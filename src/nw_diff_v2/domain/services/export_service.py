"""Export payload builders for captured artifacts."""

from __future__ import annotations

import html
from typing import Any

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services.diff_service import compute_diff_status
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.storage.files import (
    command_label_from_key,
    list_artifact_files,
    list_command_keys,
    read_output_by_key,
)


class ExportNotFoundError(RuntimeError):
    """Raised when an export target or artifacts are missing."""


def build_host_export_json(hostname: str) -> dict[str, Any]:
    """Export available v2 artifacts for the target host as JSON."""
    result: dict[str, Any] = {"hostname": hostname, "bases": {"origin": [], "dest": []}}
    for base in ("origin", "dest"):
        for path in list_artifact_files(base, hostname):
            result["bases"][base].append(
                {
                    "file": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "modified_at": path.stat().st_mtime,
                }
            )

    if not result["bases"]["origin"] and not result["bases"]["dest"]:
        raise ExportNotFoundError(f"No artifacts found for host: {hostname}")
    return result


def build_host_diff_export_json(hostname: str) -> dict[str, Any]:
    """Export per-command origin/dest status and diff summary as JSON."""
    hosts = load_hosts(settings.hosts_csv)
    host_row = next((row for row in hosts if row.host == hostname), None)
    if host_row is None:
        raise ExportNotFoundError("Hostname not found in hosts configuration")

    command_keys = sorted(
        list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
    )
    if not command_keys:
        raise ExportNotFoundError(f"No artifacts found for host: {hostname}")

    commands: list[dict[str, Any]] = []
    for command_key in command_keys:
        origin_status, origin_data = read_output_by_key("origin", hostname, command_key)
        dest_status, dest_data = read_output_by_key("dest", hostname, command_key)

        if origin_status == "available" and dest_status == "available":
            diff_status = compute_diff_status(origin_data or "", dest_data or "")
        elif origin_status != "not_found":
            diff_status = f"origin {origin_status}"
        elif dest_status != "not_found":
            diff_status = f"dest {dest_status}"
        else:
            diff_status = "file not found"

        commands.append(
            {
                "command_key": command_key,
                "command": command_label_from_key(command_key),
                "origin": {"status": origin_status},
                "dest": {"status": dest_status},
                "diff_status": diff_status,
            }
        )

    return {
        "hostname": hostname,
        "ip": host_row.ip,
        "model": host_row.model,
        "commands": commands,
    }


def render_host_export_html(hostname: str, data: dict[str, Any]) -> str:
    """Render an HTML export page for host artifact metadata."""
    safe_host = html.escape(hostname)
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='UTF-8'><title>v2 Export</title></head><body>",
        f"<h1>NW-Diff v2 Export: {safe_host}</h1>",
    ]
    for base in ("origin", "dest"):
        html_parts.append(f"<h2>{html.escape(base)}</h2><ul>")
        for item in data["bases"][base]:
            html_parts.append(
                "<li>"
                f"{html.escape(item['file'])} "
                f"(size={item['size']}, mtime={item['modified_at']})"
                "</li>"
            )
        html_parts.append("</ul>")
    html_parts.append("</body></html>")
    return "\n".join(html_parts)
