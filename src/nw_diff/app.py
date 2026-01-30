#!/usr/bin/env python3
"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

import os
import re
from pathlib import Path

from flask import (
    Flask,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from netmiko import ConnectHandler, NetMikoTimeoutException
from werkzeug.middleware.proxy_fix import ProxyFix

# Import from nw_diff modules
from nw_diff.logging_config import logger
from nw_diff.auth import require_api_token
from nw_diff.security import (
    validate_hostname,
    validate_command,
    validate_base_directory,
)
from nw_diff.storage import (
    get_file_path,
    get_diff_file_path,
    get_file_mtime,
    create_backup,
    create_unavailable_marker,
    get_file_status,
)
from nw_diff.diff import compute_diff_status, compute_diff, generate_side_by_side_html
from nw_diff.devices import (
    read_hosts_csv,
    get_device_info,
    get_commands_for_host,
)

# Determine project root directory (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "templates"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))

# Set secret key for session management (needed for flash messages)
# In production, this should be set via environment variable
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# Apply ProxyFix middleware to handle X-Forwarded-* headers from reverse proxy
# This ensures correct URL generation, HTTPS detection, and client IP logging
# when running behind nginx or other reverse proxies
# x_for=1: Trust one proxy for X-Forwarded-For (client IP)
# x_proto=1: Trust one proxy for X-Forwarded-Proto (HTTP/HTTPS)
# x_host=1: Trust one proxy for X-Forwarded-Host (original host)
# x_port=1: Trust one proxy for X-Forwarded-Port (original port)
# x_prefix=1: Trust one proxy for X-Forwarded-Prefix (URL prefix)
app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1
)


# --- Capture endpoint for individual host ---
@app.route("/capture/<base>/<hostname>", methods=["POST"])
@require_api_token
def capture(base, hostname):
    """
    Triggered when clicking the "Capture Origin" or "Capture Dest"
    button on the host list page.
    Establishes a single connection to the target device and retrieves
    output for each command (based on the device's model) before
    disconnecting. CSV reading ignores comment lines.
    Validates inputs to prevent path traversal attacks.
    """
    logger.info("Capture request received for host=%s, base=%s", hostname, base)

    if not validate_base_directory(base):
        logger.error("Invalid capture type requested: %s", base)
        return "Invalid capture type", 400

    if not validate_hostname(hostname):
        logger.error("Invalid hostname for capture: %s", hostname)
        return "Invalid hostname", 400

    commands = get_commands_for_host(hostname)
    device_info = get_device_info(hostname)
    if not device_info:
        logger.error("Could not find device info in CSV for host: %s", hostname)
        return f"Could not find device info in CSV for host: {hostname}", 404

    device = {
        "device_type": device_info["model"],
        "host": device_info["ip"],
        "username": device_info["username"],
        "port": device_info["port"],
        "password": os.environ.get("DEVICE_PASSWORD", "your_password"),
    }

    logger.info(
        "Connecting to device: %s (IP: %s, Type: %s)",
        hostname,
        device_info["ip"],
        device_info["model"],
    )

    failed_commands = []
    successful_commands = []

    try:
        connection = ConnectHandler(**device)
        logger.debug("Connection established to %s", hostname)
        connection.enable()

        # Execute all commands in a single session
        for command in commands:
            logger.debug("Executing command on %s: %s", hostname, command)
            try:
                output = connection.send_command(command, read_timeout=10)
                filepath = get_file_path(hostname, command, base)
                create_backup(filepath)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(output)
                logger.debug("Saved output for %s to: %s", command, filepath)
                successful_commands.append(command)
            except NetMikoTimeoutException:
                logger.error(
                    "Command timed out on %s: %s - marking as timeout",
                    hostname,
                    command,
                )
                # Create marker file for timeout
                filepath = get_file_path(hostname, command, base)
                create_unavailable_marker(filepath, "timeout")
                failed_commands.append((command, "timeout"))
                # Continue with next command instead of failing the entire session
                continue

        connection.disconnect()
        logger.info(
            "Completed capture for %s: %d successful, %d failed",
            hostname,
            len(successful_commands),
            len(failed_commands),
        )

        # Flash message with summary
        if failed_commands:
            flash(
                f"Capture completed for {hostname}: {len(successful_commands)} successful, "
                f"{len(failed_commands)} timed out",
                "warning",
            )
        else:
            flash(f"Successfully captured all data for {hostname}", "success")

        return redirect(url_for("host_list"))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Failed to connect to %s: %s", hostname, exc, exc_info=True)

        # Create marker files for all commands indicating connection failure
        for command in commands:
            filepath = get_file_path(hostname, command, base)
            create_unavailable_marker(filepath, "connection_failed")

        flash(
            f"Failed to connect to {hostname}: {str(exc)}. All commands marked as unavailable.",
            "error",
        )
        return redirect(url_for("host_list"))


# --- New endpoint: Capture for all devices ---
@app.route("/capture_all/<base>", methods=["POST"])
@require_api_token
def capture_all(base):
    """
    Captures data for all devices registered in hosts.csv.
    Establishes a connection for each device and retrieves the output for each command.
    CSV reading ignores comment lines.
    Validates inputs to prevent path traversal attacks.
    """
    logger.info("Capture all request received for base=%s", base)

    if not validate_base_directory(base):
        logger.error("Invalid capture type requested: %s", base)
        return "Invalid capture type", 400

    rows = read_hosts_csv()
    total_hosts = len(rows)
    success_count = 0
    failure_count = 0
    timeout_count = 0
    failed_hosts = []
    timed_out_commands = []

    logger.info("Starting capture for %d device(s)", total_hosts)

    for row in rows:
        hostname = row["host"]
        commands = get_commands_for_host(hostname)
        device_info = get_device_info(hostname)
        if not device_info:
            logger.warning("Skipping host %s - device info not found", hostname)
            failure_count += 1
            failed_hosts.append((hostname, "device info not found"))
            # Create marker files for all commands
            for command in commands:
                filepath = get_file_path(hostname, command, base)
                create_unavailable_marker(filepath, "connection_failed")
            continue

        device = {
            "device_type": device_info["model"],
            "host": device_info["ip"],
            "username": device_info["username"],
            "port": device_info["port"],
            "password": os.environ.get("DEVICE_PASSWORD", "your_password"),
        }

        logger.info(
            "Connecting to device: %s (IP: %s, Type: %s)",
            hostname,
            device_info["ip"],
            device_info["model"],
        )

        try:
            connection = ConnectHandler(**device)
            logger.debug("Connection established to %s", hostname)
            connection.enable()

            host_timeout_count = 0
            for command in commands:
                logger.debug("Executing command on %s: %s", hostname, command)
                try:
                    output = connection.send_command(command, read_timeout=10)
                    filepath = get_file_path(hostname, command, base)
                    create_backup(filepath)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(output)
                    logger.debug("Saved output for %s to: %s", command, filepath)
                except NetMikoTimeoutException:
                    logger.error(
                        "Command timed out on %s: %s - marking as timeout",
                        hostname,
                        command,
                    )
                    # Create marker file for timeout
                    filepath = get_file_path(hostname, command, base)
                    create_unavailable_marker(filepath, "timeout")
                    host_timeout_count += 1
                    timed_out_commands.append((hostname, command))
                    # Continue with next command instead of failing the entire session
                    continue

            connection.disconnect()
            logger.info(
                "Completed capture for %s: %d commands (%d timeouts)",
                hostname,
                len(commands),
                host_timeout_count,
            )
            success_count += 1
            if host_timeout_count > 0:
                timeout_count += host_timeout_count
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error connecting to %s: %s", hostname, exc, exc_info=True)
            failure_count += 1
            failed_hosts.append((hostname, str(exc)))
            # Create marker files for all commands indicating connection failure
            for command in commands:
                filepath = get_file_path(hostname, command, base)
                create_unavailable_marker(filepath, "connection_failed")
            # Continue with next device

    logger.info(
        "Capture all completed: %d successful, %d failed, %d total, %d command timeouts",
        success_count,
        failure_count,
        total_hosts,
        timeout_count,
    )

    # Flash summary message
    if failure_count > 0 or timeout_count > 0:
        summary_parts = []
        if success_count > 0:
            summary_parts.append(f"{success_count} devices successful")
        if failure_count > 0:
            summary_parts.append(f"{failure_count} devices failed to connect")
        if timeout_count > 0:
            summary_parts.append(f"{timeout_count} commands timed out")

        flash(
            f"Batch capture completed: {', '.join(summary_parts)}. "
            f"Check logs for details.",
            "warning",
        )

        # Log detailed failure info
        if failed_hosts:
            logger.info("Failed hosts: %s", ", ".join([h[0] for h in failed_hosts]))
    else:
        flash(f"Successfully captured all data from {total_hosts} devices", "success")

    return redirect(url_for("host_list"))


# --- Host List page ---
@app.route("/")
def host_list():
    """
    Displays the main host list page showing all devices and their status.
    Retrieves all hosts from CSV, computes diff status for each command pair,
    and displays modification times for origin and dest files.
    """
    logger.debug("Host list page requested")
    hosts = []
    rows = read_hosts_csv()  # CSV reading ignores comment lines
    for row in rows:
        hostname = row["host"]
        ip = row["ip"]
        commands = get_commands_for_host(hostname)
        origin_info = []
        dest_info = []
        diff_info = []
        for command in commands:
            origin_path = get_file_path(hostname, command, "origin")
            dest_path = get_file_path(hostname, command, "dest")

            # Get file status
            origin_status, origin_data = get_file_status(origin_path)
            dest_status, dest_data = get_file_status(dest_path)

            # Add origin info with status
            origin_mtime = (
                get_file_mtime(origin_path)
                if origin_status != "not_found"
                else "file not found"
            )
            origin_info.append(
                {"command": command, "mtime": origin_mtime, "status": origin_status}
            )

            # Add dest info with status
            dest_mtime = (
                get_file_mtime(dest_path)
                if dest_status != "not_found"
                else "file not found"
            )
            dest_info.append(
                {"command": command, "mtime": dest_mtime, "status": dest_status}
            )

            # Compute diff status
            if origin_status == "available" and dest_status == "available":
                status = compute_diff_status(origin_data, dest_data)
            elif origin_status in (
                "timeout",
                "connection_failed",
                "unavailable",
            ) or dest_status in ("timeout", "connection_failed", "unavailable"):
                # Use the status from the unavailable file
                if origin_status != "available":
                    status = origin_status
                else:
                    status = dest_status
            else:
                status = "file not found"

            diff_info.append({"command": command, "status": status})
        hosts.append(
            {
                "host": hostname,
                "ip": ip,
                "origin_info": origin_info,
                "dest_info": dest_info,
                "diff_info": diff_info,
            }
        )
    logger.debug("Rendered host list with %d host(s)", len(hosts))
    return render_template("host_list.html", hosts=hosts)


# --- Host Detail page ---
@app.route("/host/<hostname>")
def host_detail(hostname):
    """
    Displays detailed diff view for a specific host.
    Validates hostname to prevent path traversal attacks.
    View parameter accepts 'inline' or 'sidebyside' (default: 'inline').
    """
    logger.info("Host detail page requested for: %s", hostname)

    if not validate_hostname(hostname):
        logger.error("Invalid hostname for host detail: %s", hostname)
        return "Invalid hostname", 400

    view = request.args.get("view", "inline")
    command_results = []
    commands = get_commands_for_host(hostname)
    for command in commands:
        origin_path = get_file_path(hostname, command, "origin")
        dest_path = get_file_path(hostname, command, "dest")

        # Get file status
        origin_status, origin_data = get_file_status(origin_path)
        dest_status, dest_data = get_file_status(dest_path)

        # Get modification times
        if origin_status != "not_found":
            origin_mtime = get_file_mtime(origin_path)
        else:
            origin_mtime = "file not found"

        if dest_status != "not_found":
            dest_mtime = get_file_mtime(dest_path)
        else:
            dest_mtime = "file not found"

        # Compute diff based on file status
        if origin_status == "available" and dest_status == "available":
            diff_status, diff_html = compute_diff(origin_data, dest_data, view)
            logger.debug(
                "Computed diff for %s - command: %s, status: %s",
                hostname,
                command,
                diff_status,
            )
        elif origin_status in ("timeout", "connection_failed", "unavailable"):
            diff_status = f"origin {origin_status}"
            diff_html = (
                f"<div class='alert alert-warning'>Origin data {origin_status}</div>"
            )
            logger.warning(
                "Origin file unavailable for %s - command: %s, reason: %s",
                hostname,
                command,
                origin_status,
            )
        elif dest_status in ("timeout", "connection_failed", "unavailable"):
            diff_status = f"dest {dest_status}"
            diff_html = (
                f"<div class='alert alert-warning'>Destination data {dest_status}</div>"
            )
            logger.warning(
                "Dest file unavailable for %s - command: %s, reason: %s",
                hostname,
                command,
                dest_status,
            )
        else:
            diff_status = "file not found"
            diff_html = ""
            logger.warning(
                "Missing files for diff comparison on %s - command: %s",
                hostname,
                command,
            )

        # Save the diff file for later review
        diff_file_path = get_diff_file_path(hostname, command)
        try:
            with open(diff_file_path, "w", encoding="utf-8") as diff_file:
                diff_file.write(diff_html)
            logger.debug("Saved diff file: %s", diff_file_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error writing diff file for %s %s: %s",
                hostname,
                command,
                exc,
            )

        command_results.append(
            {
                "command": command,
                "origin_mtime": origin_mtime,
                "dest_mtime": dest_mtime,
                "diff_status": diff_status,
                "diff_html": diff_html,
            }
        )
    toggle_view = "sidebyside" if view == "inline" else "inline"
    logger.debug(
        "Rendered host detail for %s with %d command(s)", hostname, len(command_results)
    )
    return render_template(
        "host_detail.html",
        hostname=hostname,
        command_results=command_results,
        view=view,
        toggle_view=toggle_view,
    )


# --- Compare files between two hosts (origin/dest) ---
@app.route("/compare_files", methods=["GET", "POST"])
def compare_files():
    """
    Renders a form to select two hosts, directory (origin/dest), and command.
    When submitted, compares command output between two hosts for the same
    base directory (origin/dest), reads corresponding files and computes diff.
    Validates all inputs to prevent path traversal attacks.
    """
    hosts = list({row["host"] for row in read_hosts_csv()})
    error = None
    diff_html = None
    status = None
    if request.method == "POST":
        logger.info("File comparison requested")
        host1 = request.form.get("host1")
        host2 = request.form.get("host2")
        base = request.form.get("base")
        command = request.form.get("command")
        view = request.form.get("view", "sidebyside")

        if not host1 or not host2 or not base or not command:
            error = "All fields are required."
            logger.warning("File comparison failed: missing required fields")
        # Validate inputs before processing
        elif not validate_hostname(host1):
            error = f"Invalid hostname: {host1}"
            logger.warning("File comparison failed: invalid host1: %s", host1)
        elif not validate_hostname(host2):
            error = f"Invalid hostname: {host2}"
            logger.warning("File comparison failed: invalid host2: %s", host2)
        elif not validate_base_directory(base):
            error = f"Invalid base directory: {base}"
            logger.warning("File comparison failed: invalid base: %s", base)
        elif not validate_command(command):
            error = f"Invalid command: {command}"
            logger.warning("File comparison failed: invalid command: %s", command)
        else:
            try:
                path1 = get_file_path(host1, command, base)
                path2 = get_file_path(host2, command, base)
                if not os.path.exists(path1):
                    error = f"File for {host1} not found"
                    logger.error("File not found for comparison: %s", path1)
                elif not os.path.exists(path2):
                    error = f"File for {host2} not found"
                    logger.error("File not found for comparison: %s", path2)
                else:
                    with open(path1, encoding="utf-8") as f:
                        data1 = f.read()
                    with open(path2, encoding="utf-8") as f:
                        data2 = f.read()
                    if view == "sidebyside":
                        diff_html = generate_side_by_side_html(data1, data2)
                        status = compute_diff_status(data1, data2)
                    else:
                        status, diff_html = compute_diff(data1, data2, view)
                    logger.info(
                        "File comparison completed: %s vs %s, status: %s",
                        host1,
                        host2,
                        status,
                    )
            except ValueError as exc:
                error = f"Security validation failed: {exc}"
                logger.error("File comparison failed: %s", exc)
    return render_template(
        "compare_files.html",
        hosts=hosts,
        error=error,
        diff_html=diff_html,
        status=status,
    )


# --- Export diff HTML for a host ---
@app.route("/export/<hostname>")
@require_api_token
def export_diff(hostname):
    """
    Generates and returns a downloadable HTML file containing all diff results
    for the specified hostname.
    Validates hostname to prevent path traversal attacks.
    """
    if not validate_hostname(hostname):
        logger.error("Invalid hostname for export: %s", hostname)
        return "Invalid hostname", 400

    commands = get_commands_for_host(hostname)
    device_info = get_device_info(hostname)
    if not device_info:
        return "Host not found", 404

    # Sanitize hostname for filename - prevent path traversal
    safe_hostname = re.sub(r"[^\w\-]", "_", hostname)

    # Generate HTML content
    bootstrap_css = (
        "https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css"
    )
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        f"<title>Diff Export - {hostname}</title>",
        f"<link rel='stylesheet' href='{bootstrap_css}'>",
        "</head>",
        "<body>",
        "<div class='container mt-4'>",
        f"<h1>Diff Export for Host: {hostname}</h1>",
        f"<p><strong>IP Address:</strong> {device_info['ip']}</p>",
        "<hr>",
    ]

    for command in commands:
        origin_path = get_file_path(hostname, command, "origin")
        dest_path = get_file_path(hostname, command, "dest")

        # Get file status
        origin_status, origin_data = get_file_status(origin_path)
        dest_status, dest_data = get_file_status(dest_path)

        if origin_status == "available" and dest_status == "available":
            try:
                origin_mtime = get_file_mtime(origin_path)
                dest_mtime = get_file_mtime(dest_path)
                status, diff_html = compute_diff(origin_data, dest_data, "inline")

                html_parts.append("<div class='card mb-3'>")
                cmd_header = (
                    f"<div class='card-header'>"
                    f"<strong>Command:</strong> {command}</div>"
                )
                html_parts.append(cmd_header)
                html_parts.append("<div class='card-body'>")
                html_parts.append(
                    f"<p><strong>Origin Modified:</strong> {origin_mtime}</p>"
                )
                html_parts.append(
                    f"<p><strong>Dest Modified:</strong> {dest_mtime}</p>"
                )
                if status == "changes detected":
                    status_span = (
                        f"<span style='background-color: #ffff99; "
                        f"font-weight:bold; padding: 5px; "
                        f"color:black;'>{status}</span>"
                    )
                    html_parts.append(status_span)
                elif status == "identical":
                    status_span = (
                        f"<span style='background-color: #add8e6; "
                        f"font-weight:bold; padding: 5px; "
                        f"color:black;'>{status}</span>"
                    )
                    html_parts.append(status_span)
                else:
                    html_parts.append(f"<span class='badge badge-info'>{status}</span>")
                html_parts.append(f"<div class='mt-3'>{diff_html}</div>")
                html_parts.append("</div></div>")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                html_parts.append("<div class='card mb-3'>")
                cmd_header = (
                    f"<div class='card-header'>"
                    f"<strong>Command:</strong> {command}</div>"
                )
                html_parts.append(cmd_header)
                html_parts.append("<div class='card-body'>")
                html_parts.append(
                    f"<p class='text-danger'>Error reading files: {exc}</p>"
                )
                html_parts.append("</div></div>")
        else:
            # Handle unavailable files
            html_parts.append("<div class='card mb-3'>")
            cmd_header = (
                f"<div class='card-header'>"
                f"<strong>Command:</strong> {command}</div>"
            )
            html_parts.append(cmd_header)
            html_parts.append("<div class='card-body'>")

            # Display status information
            if origin_status != "available":
                origin_mtime = (
                    get_file_mtime(origin_path)
                    if origin_status != "not_found"
                    else "N/A"
                )
                html_parts.append(
                    f"<p><strong>Origin Modified:</strong> {origin_mtime} "
                    f"<span class='badge badge-warning'>{origin_status}</span></p>"
                )
            else:
                origin_mtime = get_file_mtime(origin_path)
                html_parts.append(
                    f"<p><strong>Origin Modified:</strong> {origin_mtime}</p>"
                )

            if dest_status != "available":
                dest_mtime = (
                    get_file_mtime(dest_path) if dest_status != "not_found" else "N/A"
                )
                html_parts.append(
                    f"<p><strong>Dest Modified:</strong> {dest_mtime} "
                    f"<span class='badge badge-warning'>{dest_status}</span></p>"
                )
            else:
                dest_mtime = get_file_mtime(dest_path)
                html_parts.append(
                    f"<p><strong>Dest Modified:</strong> {dest_mtime}</p>"
                )

            # Show unavailability message
            if origin_status in ("timeout", "connection_failed", "unavailable"):
                html_parts.append(
                    f"<p class='text-warning'>Origin data unavailable: {origin_status}</p>"
                )
            if dest_status in ("timeout", "connection_failed", "unavailable"):
                html_parts.append(
                    f"<p class='text-warning'>Destination data "
                    f"unavailable: {dest_status}</p>"
                )
            if origin_status == "not_found" and dest_status == "not_found":
                html_parts.append(
                    "<p class='text-danger'>Files not found for this command</p>"
                )

            html_parts.append("</div></div>")

    html_parts.extend(["</div>", "</body>", "</html>"])
    html_content = "\n".join(html_parts)

    response = make_response(html_content)
    response.headers["Content-Type"] = "text/html"
    response.headers["Content-Disposition"] = (
        f"attachment; filename={safe_hostname}-diff-export.html"
    )
    return response


# --- JSON Export API endpoint ---
@app.route("/api/export/<hostname>")
@require_api_token
def export_json(hostname):
    """
    JSON export endpoint that returns all command results, timestamps, and diff status
    for the specified hostname. Validates hostname to prevent security issues.
    """
    # Validate hostname format
    if not validate_hostname(hostname):
        logger.error("Invalid hostname for JSON export: %s", hostname)
        return jsonify({"error": "Invalid hostname"}), 400

    # Validate hostname exists in CSV
    device_info = get_device_info(hostname)
    if not device_info:
        return (
            jsonify({"error": "Hostname not found in hosts configuration"}),
            404,
        )

    commands = get_commands_for_host(hostname)
    export_data = {
        "hostname": hostname,
        "ip": device_info["ip"],
        "model": device_info.get("model", ""),
        "commands": [],
    }

    for command in commands:
        origin_path = get_file_path(hostname, command, "origin")
        dest_path = get_file_path(hostname, command, "dest")

        # Get file status
        origin_status, origin_data = get_file_status(origin_path)
        dest_status, dest_data = get_file_status(dest_path)

        if origin_status == "available" and dest_status == "available":
            try:
                origin_mtime = get_file_mtime(origin_path)
                dest_mtime = get_file_mtime(dest_path)
                status = compute_diff_status(origin_data, dest_data)

                command_data = {
                    "command": command,
                    "origin": {
                        "exists": True,
                        "timestamp": origin_mtime,
                        "status": "available",
                    },
                    "dest": {
                        "exists": True,
                        "timestamp": dest_mtime,
                        "status": "available",
                    },
                    "diff_status": status,
                }
                export_data["commands"].append(command_data)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Error reading files for command %s: %s", command, exc)
                command_data = {
                    "command": command,
                    "origin": {"exists": False, "timestamp": None, "status": "error"},
                    "dest": {"exists": False, "timestamp": None, "status": "error"},
                    "diff_status": "error",
                    "error": str(exc),
                }
                export_data["commands"].append(command_data)
        else:
            # Handle unavailable files
            origin_exists = origin_status != "not_found"
            dest_exists = dest_status != "not_found"

            command_data = {
                "command": command,
                "origin": {
                    "exists": origin_exists,
                    "timestamp": (
                        get_file_mtime(origin_path) if origin_exists else None
                    ),
                    "status": origin_status,
                },
                "dest": {
                    "exists": dest_exists,
                    "timestamp": (get_file_mtime(dest_path) if dest_exists else None),
                    "status": dest_status,
                },
                "diff_status": (
                    origin_status if origin_status != "available" else dest_status
                ),
            }
            export_data["commands"].append(command_data)

    return jsonify(export_data)


# --- Logs Web UI ---
@app.route("/logs")
@require_api_token
def logs_view():
    """
    Web UI for viewing logs.
    Displays the most recent log entries (supports limit parameter to control
    the number of lines displayed, default: 1000, max: 10000).
    """
    logger.debug("Logs view page requested")

    # Get limit from query parameter, default to 1000
    try:
        limit = int(request.args.get("limit", "1000"))
        limit = min(limit, 10000)  # Max 10000 lines
    except ValueError:
        limit = 1000

    # Import LOGS_DIR at runtime to allow test mocking
    from nw_diff.logging_config import (  # pylint: disable=import-outside-toplevel
        LOGS_DIR as current_logs_dir,
    )

    log_file_path = os.path.join(current_logs_dir, "nw-diff.log")
    lines = []
    try:
        if os.path.exists(log_file_path):
            with open(log_file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                lines = all_lines[-limit:]  # Get last N lines
        else:
            logger.warning("Log file does not exist yet: %s", log_file_path)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error reading log file: %s", exc)
        lines = [f"Error reading log file: {exc}"]

    return render_template("logs.html", log_lines=lines)


# --- Logs API Endpoint ---
@app.route("/api/logs")
@require_api_token
def logs_api():
    """
    API endpoint for programmatic access to logs.
    Returns logs in JSON format.

    Query parameters:
    - level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - limit: Maximum number of lines to return (default: 1000, max: 10000)
    - tail: If true, return the last N lines (default: true)
    """
    logger.debug("Logs API endpoint requested")

    # Get query parameters
    level_filter = request.args.get("level", "").upper()
    try:
        limit = int(request.args.get("limit", "1000"))
        limit = min(limit, 10000)  # Max 10000 lines
    except ValueError:
        limit = 1000

    tail = request.args.get("tail", "true").lower() == "true"

    # Import LOGS_DIR at runtime to allow test mocking
    from nw_diff.logging_config import (  # pylint: disable=import-outside-toplevel
        LOGS_DIR as current_logs_dir,
    )

    log_file_path = os.path.join(current_logs_dir, "nw-diff.log")
    log_entries = []

    try:
        if os.path.exists(log_file_path):
            with open(log_file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

                # Get lines based on tail parameter
                if tail:
                    lines = all_lines[-limit:]
                else:
                    lines = all_lines[:limit]

                # Filter by level if specified
                for line in lines:
                    if level_filter and level_filter not in line:
                        continue
                    log_entries.append(line.rstrip())
        else:
            logger.warning("Log file does not exist yet: %s", log_file_path)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error reading log file for API: %s", exc)
        return jsonify({"error": "Error reading log file", "logs": []}), 500

    return jsonify(
        {
            "logs": log_entries,
            "count": len(log_entries),
            "level_filter": level_filter if level_filter else None,
            "limit": limit,
        }
    )


if __name__ == "__main__":
    # Read debug mode from environment variable, default to False for security
    debug_mode = os.environ.get("APP_DEBUG", "false").lower() in {"true", "1", "yes"}

    # Read host and port from environment variables
    # Default to 127.0.0.1 for dev/single-user safety
    # Set FLASK_RUN_HOST=0.0.0.0 in container environments for network accessibility
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))

    logger.info("Starting Flask app on %s:%d (debug=%s)", host, port, debug_mode)
    app.run(host=host, port=port, debug=debug_mode)
