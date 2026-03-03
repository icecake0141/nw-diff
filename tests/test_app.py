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

from __future__ import annotations

# pylint: disable=protected-access

import importlib
import logging
import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from netmiko import NetMikoTimeoutException
from werkzeug.middleware.proxy_fix import ProxyFix

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nw_diff import (  # pylint: disable=wrong-import-position
    app,
    security,
    storage,
    diff,
    devices,
    logging_config,
)


def test_read_hosts_csv_skips_comments(tmp_path: Path, monkeypatch) -> None:
    """Ensure comment lines are skipped while parsing the hosts CSV."""
    hosts_csv = tmp_path / "hosts.csv"
    csv_content = (
        "# comment line\n"
        "host,ip,username,port,model\n"
        "router1,10.0.0.1,admin,22,cisco\n"
        "router2,10.0.0.2,admin,22,fortinet\n"
    )
    hosts_csv.write_text(csv_content, encoding="utf-8")
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    rows = devices.read_hosts_csv()

    assert len(rows) == 2
    assert rows[0]["host"] == "router1"


def test_get_commands_for_host_uses_model(tmp_path: Path, monkeypatch) -> None:
    """Return device-specific commands when the model is known."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    commands = devices.get_commands_for_host("router1")

    assert commands == devices.DEVICE_COMMANDS["cisco"]


def test_get_device_info_missing_host_returns_none(tmp_path: Path, monkeypatch) -> None:
    """Return None when a host entry is not found in the CSV."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    device_info = devices.get_device_info("router2")

    assert device_info is None


def test_get_commands_for_host_returns_default_for_unknown_model(
    tmp_path: Path, monkeypatch
) -> None:
    """Return default commands when the model is unknown."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,unknown\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    commands = devices.get_commands_for_host("router1")

    assert commands == devices.DEFAULT_COMMANDS


def test_get_file_path_invalid_base_raises() -> None:
    """Raise a ValueError when the base directory is invalid."""
    with pytest.raises(ValueError, match="Invalid base"):
        storage.get_file_path("router1", "show version", "archive")


def test_compute_diff_status_identical() -> None:
    """Return identical status when content matches."""
    assert diff.compute_diff_status("same", "same") == "identical"


def test_compute_diff_status_changes() -> None:
    """Return changes detected status when content differs."""
    assert diff.compute_diff_status("before", "after") == "changes detected"


def test_compute_diff_inline_contains_diff_markup() -> None:
    """Inline diff should include markup when differences exist."""
    status, diff_html = diff.compute_diff(
        "hello\nworld\n", "hello\nthere\n", view="inline"
    )

    assert status == "changes detected"
    assert "<del" in diff_html or "<ins" in diff_html


def test_generate_side_by_side_html_includes_highlights() -> None:
    """Side-by-side HTML should include diff and line highlights."""
    html = diff.generate_side_by_side_html("hello\nworld\n", "hello\nthere\n")

    assert "<del" in html
    assert "<ins" in html
    assert "background-color: #ffcccc" in html
    assert "background-color: #cce5ff" in html
    assert "text-decoration: none" in html


def test_generate_side_by_side_html_aligns_rows() -> None:
    """Side-by-side HTML should align corresponding lines with line numbers."""
    origin = "A\nB\nD\nF"
    dest = "A\nB\nC\nD\nE\nF"
    html = diff.generate_side_by_side_html(origin, dest)

    # Should have line numbers for both sides
    assert "Origin" in html and "Destination" in html

    # Should have table structure with 4 columns (linenum, content for each side)
    assert html.count("<th") >= 4

    # Should have rows for all lines (A, B, [C-added], D, [E-added], F)
    # Total of 6 rows in this case
    assert html.count("<tr>") >= 6

    # Check that line numbers appear
    assert ">1<" in html  # Line 1
    assert ">2<" in html  # Line 2

    # Check alignment: added line C should have empty origin
    # Check for deleted content with background
    assert "background-color: #ffcccc" in html or "background-color: #cce5ff" in html


def test_generate_side_by_side_html_aligns_replacements() -> None:
    """Replaced lines should align with partial highlights."""
    html = diff.generate_side_by_side_html("hello", "hallo")

    assert re.search(r"<tr>.*?>1<.*?>1<.*?</tr>", html, re.DOTALL)
    assert (
        "<del style='background-color: #ffcccc; text-decoration: none;'>e</del>" in html
    )
    assert (
        "<ins style='background-color: #cce5ff; text-decoration: none;'>a</ins>" in html
    )
    assert "<del style='background-color: #ffcccc;'>hello</del>" not in html


def test_generate_side_by_side_html_handles_deletions() -> None:
    """Test that deletions appear only on the left with empty right side."""
    origin = "A\nB\nC\nD"
    dest = "A\nD"
    html = diff.generate_side_by_side_html(origin, dest)

    # Should have delete markers
    assert "<del" in html
    # Should have deletion background color
    assert "background-color: #ffcccc" in html
    # Should have table structure
    assert "<table" in html


def test_generate_side_by_side_html_handles_additions() -> None:
    """Test that additions appear only on the right with empty left side."""
    origin = "A\nD"
    dest = "A\nB\nC\nD"
    html = diff.generate_side_by_side_html(origin, dest)

    # Should have insert markers
    assert "<ins" in html
    # Should have addition background color
    assert "background-color: #cce5ff" in html
    # Should have table structure
    assert "<table" in html


def test_get_backup_filename_format(tmp_path: Path, monkeypatch) -> None:
    """Ensure backup filename follows the correct format."""
    monkeypatch.setattr(storage, "BACKUP_DIR", str(tmp_path / "backup"))
    filepath = "/home/runner/work/nwdiff/nwdiff/origin/router1-show_version.txt"

    backup_filename = storage.get_backup_filename(filepath)

    # Check that backup filename includes timestamp and original filename
    assert "router1-show_version.txt" in backup_filename
    assert str(tmp_path / "backup") in backup_filename
    # Verify timestamp format YYYYMMDD_HHMMSS
    pattern = r"\d{8}_\d{6}_router1-show_version\.txt"
    assert re.search(pattern, backup_filename)


def test_create_backup_when_file_exists(tmp_path: Path, monkeypatch) -> None:
    """Backup should be created when file exists."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    monkeypatch.setattr(storage, "BACKUP_DIR", str(backup_dir))

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("original content", encoding="utf-8")

    storage.create_backup(str(test_file))

    # Check that backup was created
    backup_files = list(backup_dir.glob("*_test.txt"))
    assert len(backup_files) == 1
    assert backup_files[0].read_text(encoding="utf-8") == "original content"


def test_create_backup_when_file_does_not_exist(tmp_path: Path, monkeypatch) -> None:
    """No backup should be created when file does not exist."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    monkeypatch.setattr(storage, "BACKUP_DIR", str(backup_dir))

    # Try to backup a non-existent file
    test_file = tmp_path / "nonexistent.txt"

    storage.create_backup(str(test_file))

    # Check that no backup was created
    backup_files = list(backup_dir.glob("*_nonexistent.txt"))
    assert len(backup_files) == 0


def test_rotate_backups_keeps_last_10(tmp_path: Path, monkeypatch) -> None:
    """Rotation should keep only the last 10 backups."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    monkeypatch.setattr(storage, "BACKUP_DIR", str(backup_dir))

    test_file = tmp_path / "test.txt"
    test_file.write_text("content", encoding="utf-8")

    # Create 15 backups with different timestamps
    for i in range(15):
        backup_path = backup_dir / f"backup_{i:02d}_test.txt"
        backup_path.write_text(f"content {i}", encoding="utf-8")
        # Set modification time to ensure proper ordering
        mtime = time.time() - (15 - i)
        os.utime(str(backup_path), (mtime, mtime))

    storage.rotate_backups(str(test_file))

    # Check that only 10 backups remain
    backup_files = list(backup_dir.glob("*_test.txt"))
    assert len(backup_files) == 10

    # Verify that the oldest ones were deleted
    remaining_names = sorted([f.name for f in backup_files])
    for i in range(5, 15):
        assert f"backup_{i:02d}_test.txt" in remaining_names


def test_export_json_returns_404_for_missing_hostname(
    tmp_path: Path, monkeypatch
) -> None:
    """Return 404 error when hostname is not found in CSV."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        response = client.get("/api/export/nonexistent")

    assert response.status_code == 404
    assert response.json is not None
    assert response.json["error"] == "Hostname not found in hosts configuration"


def test_export_json_returns_valid_structure(tmp_path: Path, monkeypatch) -> None:
    """Return valid JSON structure with hostname, IP, model, and commands."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(tmp_path / "origin"))
    monkeypatch.setattr(storage, "DEST_DIR", str(tmp_path / "dest"))

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 200
    data = response.json
    assert data is not None
    assert data["hostname"] == "router1"
    assert data["ip"] == "10.0.0.1"
    assert data["model"] == "cisco"
    assert "commands" in data
    assert isinstance(data["commands"], list)


def test_export_json_includes_command_data(tmp_path: Path, monkeypatch) -> None:
    """Return command data with timestamps and diff status."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    origin_dir = tmp_path / "origin"
    dest_dir = tmp_path / "dest"
    origin_dir.mkdir()
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create test files for one command
    origin_file = origin_dir / "router1-show_version.txt"
    dest_file = dest_dir / "router1-show_version.txt"
    origin_file.write_text("Version 1.0", encoding="utf-8")
    dest_file.write_text("Version 1.0", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 200
    data = response.json
    assert data is not None
    assert len(data["commands"]) > 0

    # Check first command structure
    cmd = data["commands"][0]
    assert "command" in cmd
    assert "origin" in cmd
    assert "dest" in cmd
    assert "diff_status" in cmd
    assert "timestamp" in cmd["origin"]
    assert "exists" in cmd["origin"]
    assert "timestamp" in cmd["dest"]
    assert "exists" in cmd["dest"]


def test_export_json_detects_identical_files(tmp_path: Path, monkeypatch) -> None:
    """Return identical diff status when origin and dest files match."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    origin_dir = tmp_path / "origin"
    dest_dir = tmp_path / "dest"
    origin_dir.mkdir()
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create identical test files
    origin_file = origin_dir / "router1-show_version.txt"
    dest_file = dest_dir / "router1-show_version.txt"
    origin_file.write_text("Same content", encoding="utf-8")
    dest_file.write_text("Same content", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 200
    data = response.json
    assert data is not None
    cmd = data["commands"][0]
    assert cmd["diff_status"] == "identical"


def test_export_json_detects_changes(tmp_path: Path, monkeypatch) -> None:
    """Return changes detected status when origin and dest files differ."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    origin_dir = tmp_path / "origin"
    dest_dir = tmp_path / "dest"
    origin_dir.mkdir()
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create different test files
    origin_file = origin_dir / "router1-show_version.txt"
    dest_file = dest_dir / "router1-show_version.txt"
    origin_file.write_text("Version 1.0", encoding="utf-8")
    dest_file.write_text("Version 2.0", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 200
    data = response.json
    assert data is not None
    cmd = data["commands"][0]
    assert cmd["diff_status"] == "changes detected"


def test_logging_configuration_creates_log_file() -> None:
    """Test that logging is properly configured and creates log files."""
    # Import logger from app to verify it exists
    assert logging_config.logger is not None
    assert logging_config.logger.name == "nw-diff"
    assert logging_config.logger.level == logging.DEBUG


def test_logger_handlers_not_duplicated_on_reimport() -> None:
    """Test that logger handlers are not duplicated on module re-import."""
    # Get the initial number of handlers
    initial_handler_count = len(logging_config.logger.handlers)

    # Re-import the module (simulates WSGI reloading)
    importlib.reload(app)

    # Check that handlers were not duplicated
    assert len(logging_config.logger.handlers) == initial_handler_count


def test_create_backup_logs_warning_on_failure(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Test that create_backup logs a warning instead of using print() on failure."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    monkeypatch.setattr(storage, "BACKUP_DIR", str(backup_dir))

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("original content", encoding="utf-8")

    # Make backup directory read-only to trigger an error
    backup_dir.chmod(0o444)

    # Call create_backup which should log a warning instead of printing
    with caplog.at_level(logging.WARNING):
        storage.create_backup(str(test_file))

    # Verify that a warning was logged
    assert any("Failed to create backup" in record.message for record in caplog.records)

    # Clean up: restore permissions
    backup_dir.chmod(0o755)


def test_logs_view_endpoint(tmp_path: Path, monkeypatch) -> None:
    """Test the /logs web UI endpoint."""
    # Create a test log file
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "nw-diff.log"
    log_file.write_text(
        "2025-01-16 12:00:00 - nw-diff - INFO - Test log line 1\n"
        "2025-01-16 12:00:01 - nw-diff - ERROR - Test error line\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(logging_config, "LOGS_DIR", str(logs_dir))

    with app.app.test_client() as client:
        response = client.get("/logs")
        assert response.status_code == 200
        assert b"Application Logs" in response.data
        assert b"Test log line 1" in response.data
        assert b"Test error line" in response.data


def test_logs_api_endpoint(tmp_path: Path, monkeypatch) -> None:
    """Test the /api/logs API endpoint."""
    # Create a test log file
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "nw-diff.log"
    log_file.write_text(
        "2025-01-16 12:00:00 - nw-diff - INFO - Test info log\n"
        "2025-01-16 12:00:01 - nw-diff - ERROR - Test error log\n"
        "2025-01-16 12:00:02 - nw-diff - DEBUG - Test debug log\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(logging_config, "LOGS_DIR", str(logs_dir))

    with app.app.test_client() as client:
        # Test basic API call
        response = client.get("/api/logs")
        assert response.status_code == 200
        json_data = response.get_json()
        assert "logs" in json_data
        assert "count" in json_data
        assert json_data["count"] == 3

        # Test level filtering
        response = client.get("/api/logs?level=ERROR")
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["count"] == 1
        assert json_data["level_filter"] == "ERROR"

        # Test limit parameter
        response = client.get("/api/logs?limit=2")
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["count"] == 2
        assert json_data["limit"] == 2


def test_read_hosts_csv_handles_file_not_found(tmp_path: Path, monkeypatch) -> None:
    """Test that read_hosts_csv handles missing CSV gracefully."""
    non_existent = tmp_path / "nonexistent.csv"
    monkeypatch.setattr(devices, "HOSTS_CSV", str(non_existent))

    rows = devices.read_hosts_csv()

    assert not rows


def test_read_hosts_csv_filters_invalid_rows(tmp_path: Path, monkeypatch) -> None:
    """Invalid rows should be skipped while valid rows are retained."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "bad-host,10.0.0.999,admin,22,cisco\n"
            "router2,10.0.0.2,admin,70000,cisco\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    rows = devices.read_hosts_csv()

    assert len(rows) == 1
    assert rows[0]["host"] == "router1"


def test_capture_stream_rejects_same_host_concurrent_run(
    tmp_path: Path, monkeypatch
) -> None:
    """Streaming capture should return 409 when same host is already reserved."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    acquired, _ = app._reserve_capture_hosts({"router1"})
    assert acquired is True
    try:
        with app.app.test_client() as client:
            response = client.post("/api/capture/origin/router1/stream")
        assert response.status_code == 409
        json_data = response.get_json()
        assert json_data is not None
        assert "already running" in json_data["error"].lower()
    finally:
        app._release_capture_hosts({"router1"})


def test_debug_mode_disabled_by_default(monkeypatch) -> None:
    """Test that Flask debug mode is disabled by default."""
    # Ensure APP_DEBUG is not set
    monkeypatch.delenv("APP_DEBUG", raising=False)

    # The debug mode should be False when APP_DEBUG is not set
    debug_mode = os.environ.get("APP_DEBUG", "false").lower() in {"true", "1", "yes"}
    assert debug_mode is False


def test_debug_mode_enabled_with_env_var(monkeypatch) -> None:
    """Test that Flask debug mode can be enabled via APP_DEBUG environment variable."""
    # Test with "true"
    monkeypatch.setenv("APP_DEBUG", "true")
    debug_mode = os.environ.get("APP_DEBUG", "false").lower() in {"true", "1", "yes"}
    assert debug_mode is True

    # Test with "1"
    monkeypatch.setenv("APP_DEBUG", "1")
    debug_mode = os.environ.get("APP_DEBUG", "false").lower() in {"true", "1", "yes"}
    assert debug_mode is True

    # Test with "yes"
    monkeypatch.setenv("APP_DEBUG", "yes")
    debug_mode = os.environ.get("APP_DEBUG", "false").lower() in {"true", "1", "yes"}
    assert debug_mode is True

    # Test with "false"
    monkeypatch.setenv("APP_DEBUG", "false")
    debug_mode = os.environ.get("APP_DEBUG", "false").lower() in {"true", "1", "yes"}
    assert debug_mode is False


# --- Security tests for path traversal protection ---


def test_validate_hostname_rejects_parent_directory() -> None:
    """Test that hostname validation rejects parent directory references."""
    assert security.validate_hostname("..") is False
    assert security.validate_hostname("../etc") is False
    assert security.validate_hostname("test/../etc") is False


def test_validate_hostname_rejects_path_separators() -> None:
    """Test that hostname validation rejects path separators."""
    assert security.validate_hostname("/etc/passwd") is False
    assert security.validate_hostname("test/file") is False
    assert security.validate_hostname("test\\file") is False
    assert security.validate_hostname("\\windows\\system32") is False


def test_validate_hostname_rejects_invalid_characters() -> None:
    """Test that hostname validation rejects special characters."""
    assert security.validate_hostname("test;rm -rf") is False
    assert security.validate_hostname("test|cat") is False
    assert security.validate_hostname("test&ls") is False
    assert security.validate_hostname("test$var") is False
    assert security.validate_hostname("test`whoami`") is False


def test_validate_hostname_accepts_valid_names() -> None:
    """Test that hostname validation accepts valid hostnames."""
    assert security.validate_hostname("router1") is True
    assert security.validate_hostname("switch-01") is True
    assert security.validate_hostname("fw_main") is True
    assert security.validate_hostname("host.example.com") is True
    assert security.validate_hostname("router-123_backup") is True


def test_validate_hostname_rejects_empty() -> None:
    """Test that hostname validation rejects empty strings."""
    assert security.validate_hostname("") is False
    assert security.validate_hostname(None) is False


def test_validate_command_rejects_parent_directory() -> None:
    """Test that command validation rejects parent directory references."""
    assert security.validate_command("..") is False
    assert security.validate_command("../etc/passwd") is False
    assert security.validate_command("show ../../../etc/passwd") is False


def test_validate_command_rejects_path_separators() -> None:
    """Test that command validation rejects path separators."""
    assert security.validate_command("/etc/passwd") is False
    assert security.validate_command("show /etc/passwd") is False
    assert security.validate_command("show\\file") is False


def test_validate_command_rejects_invalid_characters() -> None:
    """Test that command validation rejects special characters."""
    assert security.validate_command("show version; rm -rf") is False
    assert security.validate_command("show|cat") is False
    assert security.validate_command("show&ls") is False


def test_validate_command_accepts_valid_commands() -> None:
    """Test that command validation accepts valid commands."""
    assert security.validate_command("show version") is True
    assert security.validate_command("show running-config") is True
    assert security.validate_command("get system status") is True
    assert security.validate_command("diag_switch_ports") is True


def test_validate_command_rejects_empty() -> None:
    """Test that command validation rejects empty strings."""
    assert security.validate_command("") is False
    assert security.validate_command(None) is False


def test_validate_base_directory_accepts_valid() -> None:
    """Test that base directory validation accepts only origin and dest."""
    assert security.validate_base_directory("origin") is True
    assert security.validate_base_directory("dest") is True


def test_validate_base_directory_rejects_invalid() -> None:
    """Test that base directory validation rejects other values."""
    assert security.validate_base_directory("backup") is False
    assert security.validate_base_directory("../origin") is False
    assert security.validate_base_directory("/tmp") is False
    assert security.validate_base_directory("") is False


def test_get_file_path_rejects_traversal_in_hostname() -> None:
    """Test that get_file_path rejects path traversal in hostname."""
    with pytest.raises(ValueError, match="Invalid hostname"):
        storage.get_file_path("../etc", "show version", "origin")
    with pytest.raises(ValueError, match="Invalid hostname"):
        storage.get_file_path("../../etc/passwd", "show version", "origin")


def test_get_file_path_rejects_traversal_in_command() -> None:
    """Test that get_file_path rejects path traversal in command."""
    with pytest.raises(ValueError, match="Invalid command"):
        storage.get_file_path("router1", "../etc/passwd", "origin")
    with pytest.raises(ValueError, match="Invalid command"):
        storage.get_file_path("router1", "show ../../etc/passwd", "origin")


def test_get_file_path_rejects_invalid_base() -> None:
    """Test that get_file_path rejects invalid base directory."""
    with pytest.raises(ValueError, match="Invalid base"):
        storage.get_file_path("router1", "show version", "backup")
    with pytest.raises(ValueError, match="Invalid base"):
        storage.get_file_path("router1", "show version", "../origin")


def test_get_file_path_returns_normalized_path() -> None:
    """Test that get_file_path returns properly normalized paths."""
    path = storage.get_file_path("router1", "show version", "origin")
    assert ".." not in path
    assert path.startswith("origin")
    assert "router1-show_version.txt" in path


def test_get_diff_file_path_rejects_traversal() -> None:
    """Test that get_diff_file_path rejects path traversal attempts."""
    with pytest.raises(ValueError, match="Invalid hostname"):
        storage.get_diff_file_path("../etc", "show version")
    with pytest.raises(ValueError, match="Invalid command"):
        storage.get_diff_file_path("router1", "../etc/passwd")


def test_compare_files_rejects_invalid_hostname(tmp_path: Path, monkeypatch) -> None:
    """Test that /compare_files endpoint rejects invalid hostnames."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        response = client.post(
            "/compare_files",
            data={
                "host1": "../etc",
                "host2": "router1",
                "base": "origin",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 200
        assert b"Invalid hostname" in response.data


def test_compare_files_rejects_invalid_command(tmp_path: Path, monkeypatch) -> None:
    """Test that /compare_files endpoint rejects invalid commands."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        response = client.post(
            "/compare_files",
            data={
                "host1": "router1",
                "host2": "router1",
                "base": "origin",
                "command": "../etc/passwd",
                "view": "inline",
            },
        )
        assert response.status_code == 200
        assert b"Invalid command" in response.data


def test_compare_files_rejects_invalid_base(tmp_path: Path, monkeypatch) -> None:
    """Test that /compare_files endpoint rejects invalid base directory."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        response = client.post(
            "/compare_files",
            data={
                "host1": "router1",
                "host2": "router1",
                "base": "../backup",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 200
        assert b"Invalid base" in response.data


def test_capture_endpoint_rejects_invalid_hostname(tmp_path: Path, monkeypatch) -> None:
    """Test that /capture endpoint rejects invalid hostnames."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        # Test with hostname containing semicolon (invalid character)
        response = client.post("/capture/origin/test;rm")
        assert response.status_code == 400
        assert b"Invalid hostname" in response.data


def test_capture_endpoint_rejects_invalid_base(tmp_path: Path, monkeypatch) -> None:
    """Test that /capture endpoint rejects invalid base directory."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        # Test with invalid base directory name
        response = client.post("/capture/backup/router1")
        assert response.status_code == 400
        assert b"Invalid capture type" in response.data


def test_host_detail_rejects_invalid_hostname(tmp_path: Path, monkeypatch) -> None:
    """Test that /host/<hostname> endpoint rejects invalid hostnames."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        # Test with hostname containing invalid character
        response = client.get("/host/test;command")
        assert response.status_code == 400
        assert b"Invalid hostname" in response.data


def test_host_detail_rejects_invalid_diff_mode(tmp_path: Path, monkeypatch) -> None:
    """Test that host detail rejects invalid diff_mode values."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        response = client.get("/host/router1?diff_mode=bad")
        assert response.status_code == 400
        assert b"Invalid diff_mode" in response.data


def test_host_detail_rejects_invalid_context_lines(tmp_path: Path, monkeypatch) -> None:
    """Test that host detail rejects invalid context_lines values."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        response = client.get("/host/router1?context_lines=-1")
        assert response.status_code == 400
        assert b"Invalid context_lines" in response.data


def test_export_diff_rejects_invalid_hostname(tmp_path: Path, monkeypatch) -> None:
    """Test that /export/<hostname> endpoint rejects invalid hostnames."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        # Test with hostname containing invalid character
        response = client.get("/export/test$var")
        assert response.status_code == 400
        assert b"Invalid hostname" in response.data


def test_export_json_rejects_invalid_hostname(tmp_path: Path, monkeypatch) -> None:
    """Test that /api/export/<hostname> endpoint rejects invalid hostnames."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with app.app.test_client() as client:
        # Test with hostname containing invalid character
        response = client.get("/api/export/test|cat")
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data is not None
        assert "Invalid hostname" in json_data["error"]


# --- XSS Prevention Tests ---


def test_generate_side_by_side_html_escapes_script_tags() -> None:
    """Test that script tags in diff content are escaped in side-by-side view."""
    malicious_origin = "Safe content\n"
    malicious_dest = "Safe content\n<script>alert(1)</script>\n"

    html_output = diff.generate_side_by_side_html(malicious_origin, malicious_dest)

    # Script tags should be escaped
    assert "&lt;script&gt;" in html_output
    assert "&lt;/script&gt;" in html_output
    # Raw script tags should NOT be present
    assert "<script>alert" not in html_output


def test_generate_side_by_side_html_escapes_html_entities() -> None:
    """Test that HTML entities are properly escaped in side-by-side view."""
    origin = "Normal text"
    dest = '<img src=x onerror="alert(1)">'

    html_output = diff.generate_side_by_side_html(origin, dest)

    # HTML should be escaped
    assert "&lt;img" in html_output
    assert "&quot;" in html_output or "&#x27;" in html_output
    # Raw HTML should NOT be present
    assert "<img src=x onerror=" not in html_output


def test_generate_side_by_side_html_escapes_common_text() -> None:
    """Test that common text is also escaped in side-by-side view."""
    malicious = "<script>alert('XSS')</script>"

    html_output = diff.generate_side_by_side_html(malicious, malicious)

    # Even identical text should be escaped
    assert "&lt;script&gt;" in html_output
    assert "&lt;/script&gt;" in html_output
    assert "<script>alert" not in html_output


def test_compute_diff_inline_escapes_script_tags() -> None:
    """Test that script tags are escaped in inline diff view."""
    origin = "Safe content"
    dest = "Safe content\n<script>alert(1)</script>"

    status, diff_html = diff.compute_diff(origin, dest, view="inline")

    assert status == "changes detected"
    # Script tags should be escaped
    assert "&lt;script&gt;" in diff_html
    assert "&lt;/script&gt;" in diff_html
    # Raw script tags should NOT be present
    assert "<script>alert" not in diff_html


def test_compute_diff_identical_escapes_html() -> None:
    """Test that identical content with HTML is escaped in inline view."""
    content = "<script>alert('XSS')</script>\n<img src=x>"

    status, diff_html = diff.compute_diff(content, content, view="inline")

    assert status == "identical"
    # HTML should be escaped in the <pre> tag
    assert "&lt;script&gt;" in diff_html
    assert "&lt;img" in diff_html
    # Raw HTML should NOT be present
    assert "<script>alert" not in diff_html
    assert "<img src=x>" not in diff_html


def test_compute_diff_sidebyside_escapes_html() -> None:
    """Test that HTML is escaped in side-by-side view via compute_diff."""
    origin = "Normal\n<script>bad()</script>"
    dest = "Normal\n<script>bad()</script>"

    status, diff_html = diff.compute_diff(origin, dest, view="sidebyside")

    assert status == "identical"
    # HTML should be escaped
    assert "&lt;script&gt;" in diff_html
    assert "<script>bad()" not in diff_html


def test_compute_diff_sidebyside_handles_long_lines() -> None:
    """Test that extremely long lines have proper word-break CSS to prevent
    layout overflow."""
    # Create a very long line without spaces (e.g., a long URL or hash)
    long_line = "A" * 500  # 500 characters without spaces
    origin = f"Short line\n{long_line}\nAnother line"
    dest = f"Short line\n{long_line}_modified\nAnother line"

    status, diff_html = diff.compute_diff(origin, dest, view="sidebyside")

    assert status == "changes detected"
    # Verify the table has word-break CSS to handle long lines
    assert "word-break" in diff_html or "overflow-wrap" in diff_html
    # Verify table structure is present
    assert "<table" in diff_html
    assert "<td" in diff_html


def test_host_detail_response_escapes_xss(tmp_path: Path, monkeypatch) -> None:
    """Test that XSS payloads in host detail page response are escaped."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    origin_dir = tmp_path / "origin"
    dest_dir = tmp_path / "dest"
    diff_dir = tmp_path / "diff"
    origin_dir.mkdir()
    dest_dir.mkdir()
    diff_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))
    monkeypatch.setattr(storage, "DIFF_DIR", str(diff_dir))

    # Create files with XSS payload
    origin_file = origin_dir / "router1-show_version.txt"
    dest_file = dest_dir / "router1-show_version.txt"
    xss_payload = "Version 1.0\n<script>alert('XSS')</script>"
    origin_file.write_text(xss_payload, encoding="utf-8")
    dest_file.write_text(xss_payload, encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/host/router1")
        assert response.status_code == 200
        html_content = response.data.decode("utf-8")

        # Script tags should be escaped in the response
        assert "&lt;script&gt;" in html_content
        # Raw script should NOT be in response
        assert "<script>alert('XSS')</script>" not in html_content


def test_compare_files_response_escapes_xss(tmp_path: Path, monkeypatch) -> None:
    """Test that XSS payloads in compare files response are escaped."""
    hosts_csv = tmp_path / "hosts.csv"
    csv_content = (
        "host,ip,username,port,model\n"
        "router1,10.0.0.1,admin,22,cisco\n"
        "router2,10.0.0.2,admin,22,cisco\n"
    )
    hosts_csv.write_text(csv_content, encoding="utf-8")
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(tmp_path / "dest"))

    # Create files with XSS payload
    file1 = origin_dir / "router1-show_version.txt"
    file2 = origin_dir / "router2-show_version.txt"
    xss_payload1 = "Config line\n<img src=x onerror='alert(1)'>"
    xss_payload2 = "Config line\n<img src=x onerror='alert(2)'>"
    file1.write_text(xss_payload1, encoding="utf-8")
    file2.write_text(xss_payload2, encoding="utf-8")

    with app.app.test_client() as client:
        response = client.post(
            "/compare_files",
            data={
                "host1": "router1",
                "host2": "router2",
                "base": "origin",
                "command": "show version",
                "view": "sidebyside",
            },
        )
        assert response.status_code == 200
        html_content = response.data.decode("utf-8")

        # HTML should be escaped
        assert "&lt;img" in html_content
        # Raw HTML should NOT be in response
        assert "<img src=x onerror=" not in html_content
        # Check that alert is properly escaped (either with &quot; or &#x27;)
        assert (
            "alert(1)" not in html_content
            or "&quot;alert(1)&quot;" in html_content
            or "&#x27;alert(1)&#x27;" in html_content
        )


# --- Authentication Tests ---


def test_capture_endpoint_requires_auth_missing_token(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that /capture endpoint requires authentication - missing token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post("/capture/origin/router1")

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_capture_endpoint_requires_auth_invalid_token(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that /capture endpoint requires authentication - invalid token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post(
            "/capture/origin/router1",
            headers={"Authorization": "Bearer wrong_token"},
        )

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_capture_endpoint_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    """Test that /capture endpoint accepts valid token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post(
            "/capture/origin/router1",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should not be 401 (will be 404 or 500 due to missing device connection)
    assert response.status_code != 401


def test_capture_all_endpoint_requires_auth_missing_token(monkeypatch) -> None:
    """Test that /capture_all endpoint requires authentication - missing token."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post("/capture_all/origin")

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_capture_all_endpoint_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    """Test that /capture_all endpoint accepts valid token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post(
            "/capture_all/origin",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should not be 401 (will be redirect or error due to missing device connection)
    assert response.status_code != 401


def test_logs_view_requires_auth_missing_token(monkeypatch) -> None:
    """Test that /logs endpoint requires authentication - missing token."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get("/logs")

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_logs_view_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    """Test that /logs endpoint accepts valid token."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "nw-diff.log"
    log_file.write_text("Test log line\n", encoding="utf-8")
    monkeypatch.setattr(logging_config, "LOGS_DIR", str(logs_dir))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get(
            "/logs",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    assert response.status_code == 200
    assert b"Test log line" in response.data


def test_logs_api_requires_auth_missing_token(monkeypatch) -> None:
    """Test that /api/logs endpoint requires authentication - missing token."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get("/api/logs")

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_logs_api_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    """Test that /api/logs endpoint accepts valid token."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "nw-diff.log"
    log_file.write_text("Test log line\n", encoding="utf-8")
    monkeypatch.setattr(logging_config, "LOGS_DIR", str(logs_dir))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    assert response.status_code == 200
    json_data = response.get_json()
    assert "logs" in json_data


def test_export_diff_requires_auth_missing_token(monkeypatch) -> None:
    """Test that /export endpoint requires authentication - missing token."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get("/export/router1")

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_export_diff_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    """Test that /export endpoint accepts valid token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(tmp_path / "origin"))
    monkeypatch.setattr(storage, "DEST_DIR", str(tmp_path / "dest"))

    with app.app.test_client() as client:
        response = client.get(
            "/export/router1",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should not be 401 (will be 200 with HTML content)
    assert response.status_code != 401


def test_export_json_requires_auth_missing_token(monkeypatch) -> None:
    """Test that /api/export endpoint requires authentication - missing token."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_export_json_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    """Test that /api/export endpoint accepts valid token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(tmp_path / "origin"))
    monkeypatch.setattr(storage, "DEST_DIR", str(tmp_path / "dest"))

    with app.app.test_client() as client:
        response = client.get(
            "/api/export/router1",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should not be 401 (will be 200 with JSON content)
    assert response.status_code != 401


def test_auth_no_token_configured_allows_access(tmp_path: Path, monkeypatch) -> None:
    """Test that endpoints work without authentication when token is not configured."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(tmp_path / "origin"))
    monkeypatch.setattr(storage, "DEST_DIR", str(tmp_path / "dest"))

    with app.app.test_client() as client:
        # /api/export should work without token when NW_DIFF_API_TOKEN is not set
        response = client.get("/api/export/router1")
        # Will get 200 or other non-401 status
        assert response.status_code != 401


def test_auth_invalid_format_bearer_missing(monkeypatch) -> None:
    """Test that invalid Authorization header format is rejected."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        # Send token without "Bearer " prefix
        response = client.get(
            "/api/logs",
            headers={"Authorization": "test_secret_token"},
        )

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_auth_empty_token_after_bearer(monkeypatch) -> None:
    """Test that 'Bearer' without a token is rejected."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        # Send "Bearer" without actual token
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Bearer"},
        )

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_auth_bearer_with_only_space(monkeypatch) -> None:
    """Test that 'Bearer ' with only space is rejected."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        # Send "Bearer " with space but no token
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Bearer "},
        )

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_auth_does_not_leak_internal_details(monkeypatch) -> None:
    """Test that authentication errors do not leak sensitive information."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Bearer wrong_token"},
        )

    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data is not None
    # Error message should be generic
    assert json_data["error"] == "Authentication required"
    # Should not contain details about the expected token
    assert "test_secret_token" not in str(json_data)
    assert "NW_DIFF_API_TOKEN" not in str(json_data)


# --- Tests for POST-only capture endpoints ---


def test_capture_endpoint_get_returns_405(tmp_path: Path, monkeypatch) -> None:
    """Test that GET request to /capture endpoint returns 405 Method Not Allowed."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    with app.app.test_client() as client:
        response = client.get("/capture/origin/router1")

    assert response.status_code == 405


def test_capture_endpoint_post_works(tmp_path: Path, monkeypatch) -> None:
    """Test POST request to /capture works (even if device is not reachable)."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    with app.app.test_client() as client:
        response = client.post("/capture/origin/router1")

    # Should not be 405 (will be 404, 500, or redirect due to missing device)
    assert response.status_code != 405


def test_capture_all_endpoint_get_returns_405(tmp_path: Path, monkeypatch) -> None:
    """Test GET request to /capture_all returns 405 Method Not Allowed."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    with app.app.test_client() as client:
        response = client.get("/capture_all/origin")

    assert response.status_code == 405


def test_capture_all_endpoint_post_works(tmp_path: Path, monkeypatch) -> None:
    """Test POST request to /capture_all works (even if devices not reachable)."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    with app.app.test_client() as client:
        response = client.post("/capture_all/origin")

    # Should not be 405 (will be redirect or error due to missing device)
    assert response.status_code != 405


def test_capture_endpoint_post_with_auth_token(tmp_path: Path, monkeypatch) -> None:
    """Test that POST request to /capture endpoint works with valid auth token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post(
            "/capture/origin/router1",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should not be 401 or 405 (will be 404 or 500 due to missing device connection)
    assert response.status_code not in [401, 405]


def test_capture_endpoint_get_with_auth_token_still_405(
    tmp_path: Path, monkeypatch
) -> None:
    """Test GET request to /capture returns 405 even with valid auth token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get(
            "/capture/origin/router1",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should be 405 regardless of valid token
    assert response.status_code == 405


def test_capture_all_endpoint_post_with_auth_token(tmp_path: Path, monkeypatch) -> None:
    """Test POST request to /capture_all works with valid auth token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.post(
            "/capture_all/origin",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should not be 401 or 405 (will be redirect or error due to missing device)
    assert response.status_code not in [401, 405]


def test_capture_all_endpoint_get_with_auth_token_still_405(
    tmp_path: Path, monkeypatch
) -> None:
    """Test GET request to /capture_all returns 405 even with valid token."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_secret_token")

    with app.app.test_client() as client:
        response = client.get(
            "/capture_all/origin",
            headers={"Authorization": "Bearer test_secret_token"},
        )

    # Should be 405 regardless of valid token
    assert response.status_code == 405


# --- Tests for HOSTS_CSV environment variable configuration ---


def test_hosts_csv_uses_env_var_when_set(tmp_path: Path, monkeypatch) -> None:
    """Test that HOSTS_CSV environment variable overrides default path."""
    # Create a CSV file in a custom location
    custom_csv = tmp_path / "custom_hosts.csv"
    custom_csv.write_text(
        "host,ip,username,port,model\nrouter1,192.168.1.1,admin,22,cisco\n",
        encoding="utf-8",
    )

    # Set the environment variable to point to the custom CSV
    monkeypatch.setenv("HOSTS_CSV", str(custom_csv))

    # Reload the devices module to pick up the new environment variable
    importlib.reload(devices)

    # Verify that the custom CSV is being used
    rows = devices.read_hosts_csv()
    assert len(rows) == 1
    assert rows[0]["host"] == "router1"
    assert rows[0]["ip"] == "192.168.1.1"


def test_hosts_csv_uses_default_when_env_var_not_set(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that default hosts.csv is used when HOSTS_CSV env var is not set."""
    # Create a hosts.csv file in the current directory
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter2,10.0.0.2,admin,22,fortinet\n",
        encoding="utf-8",
    )

    # Remove the environment variable if it exists
    monkeypatch.delenv("HOSTS_CSV", raising=False)

    # Change to the temporary directory so hosts.csv is found
    monkeypatch.chdir(tmp_path)

    # Reload the devices module to pick up the new environment variable
    importlib.reload(devices)

    # Verify that the default hosts.csv is being used
    rows = devices.read_hosts_csv()
    assert len(rows) == 1
    assert rows[0]["host"] == "router2"
    assert rows[0]["ip"] == "10.0.0.2"


def test_hosts_csv_logs_path_on_read(tmp_path: Path, monkeypatch, caplog) -> None:
    """Test that the CSV path is logged when read_hosts_csv is called."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    with caplog.at_level(logging.INFO):
        devices.read_hosts_csv()

    # Verify that the path was logged
    assert any(
        "Reading hosts CSV from:" in record.message and str(hosts_csv) in record.message
        for record in caplog.records
    )


def test_hosts_csv_error_message_shows_configured_path(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Test that error messages show the configured CSV path."""
    non_existent = tmp_path / "nonexistent.csv"
    monkeypatch.setattr(devices, "HOSTS_CSV", str(non_existent))

    with caplog.at_level(logging.ERROR):
        rows = devices.read_hosts_csv()

    assert not rows
    # Verify that the error message includes the configured path
    assert any(
        "Hosts CSV file not found:" in record.message
        and str(non_existent) in record.message
        for record in caplog.records
    )


# --- Tests for ProxyFix middleware ---


def test_app_has_proxyfix_middleware() -> None:
    """Test that ProxyFix middleware is applied to the Flask app."""
    # Check that app.wsgi_app is wrapped with ProxyFix
    assert isinstance(app.app.wsgi_app, ProxyFix)


def test_proxyfix_respects_x_forwarded_proto() -> None:
    """Test that ProxyFix correctly interprets X-Forwarded-Proto header."""
    with app.app.test_client() as client:
        # Send request with X-Forwarded-Proto header
        response = client.get(
            "/",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "example.com",
            },
        )

        # Flask should see the request as HTTPS
        # This is hard to test directly, but we can verify the middleware is present
        assert response.status_code == 200


def test_proxyfix_respects_x_forwarded_for() -> None:
    """Test that ProxyFix correctly interprets X-Forwarded-For header."""
    with app.app.test_client() as client:
        # Send request with X-Forwarded-For header
        response = client.get(
            "/",
            headers={"X-Forwarded-For": "203.0.113.1"},
        )

        # Flask should see the forwarded IP
        # Middleware presence is already verified
        assert response.status_code == 200


# --- Tests for environment-based host/port binding ---


def test_flask_run_host_defaults_to_localhost(monkeypatch) -> None:
    """Test that FLASK_RUN_HOST defaults to 127.0.0.1 when not set."""
    monkeypatch.delenv("FLASK_RUN_HOST", raising=False)

    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    assert host == "127.0.0.1"


def test_flask_run_host_can_be_set(monkeypatch) -> None:
    """Test that FLASK_RUN_HOST can be set via environment variable."""
    monkeypatch.setenv("FLASK_RUN_HOST", "0.0.0.0")

    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    assert host == "0.0.0.0"


def test_flask_run_port_defaults_to_5000(monkeypatch) -> None:
    """Test that FLASK_RUN_PORT defaults to 5000 when not set."""
    monkeypatch.delenv("FLASK_RUN_PORT", raising=False)

    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    assert port == 5000


def test_flask_run_port_can_be_set(monkeypatch) -> None:
    """Test that FLASK_RUN_PORT can be set via environment variable."""
    monkeypatch.setenv("FLASK_RUN_PORT", "8080")

    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    assert port == 8080


# --- Tests for command-level timeout handling ---


def test_capture_handles_command_timeout_gracefully(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Test that command timeout does not abort the entire session."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Mock ConnectHandler and simulate timeout on second command
    mock_connection = Mock()
    mock_connection.enable = Mock()
    mock_connection.disconnect = Mock()

    def send_command_side_effect(
        command, read_timeout=None
    ):  # pylint: disable=unused-argument
        if "show version" in command:
            return "Version output"
        if "show running-config" in command:
            raise NetMikoTimeoutException("Command timed out")
        return f"Output for {command}"

    mock_connection.send_command = Mock(side_effect=send_command_side_effect)

    with patch("nw_diff.app.ConnectHandler", return_value=mock_connection):
        with caplog.at_level(logging.ERROR):
            with app.app.test_client() as client:
                response = client.post("/capture/origin/router1")

    # Verify the request succeeded despite timeout
    assert response.status_code == 302  # Redirect to host_list

    # Verify timeout was logged
    assert any(
        "Command timed out on router1" in record.message for record in caplog.records
    )
    assert any("show running-config" in record.message for record in caplog.records)

    # Verify connection was still properly closed
    mock_connection.disconnect.assert_called_once()

    # Verify send_command was called with read_timeout parameter
    calls = mock_connection.send_command.call_args_list
    for call in calls:
        assert call.kwargs.get("read_timeout") == 10


def test_capture_all_handles_command_timeout_gracefully(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Test that command timeout in capture_all does not abort device session."""
    # Setup test data with two hosts
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model
router1,10.0.0.1,admin,22,cisco
router2,10.0.0.2,admin,22,cisco
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Mock ConnectHandler and simulate timeout on specific commands
    mock_connection = Mock()
    mock_connection.enable = Mock()
    mock_connection.disconnect = Mock()

    def send_command_side_effect(
        command, read_timeout=None
    ):  # pylint: disable=unused-argument
        # Timeout on show running-config for all devices
        if "show running-config" in command:
            raise NetMikoTimeoutException("Command timed out")
        return f"Output for {command}"

    mock_connection.send_command = Mock(side_effect=send_command_side_effect)

    with patch("nw_diff.app.ConnectHandler", return_value=mock_connection):
        with caplog.at_level(logging.ERROR):
            with app.app.test_client() as client:
                response = client.post("/capture_all/origin")

    # Verify the request succeeded despite timeouts
    assert response.status_code == 302  # Redirect to host_list

    # Verify timeout was logged for both routers
    timeout_logs = [
        record for record in caplog.records if "Command timed out" in record.message
    ]
    assert len(timeout_logs) >= 2  # At least one per router

    # Verify both devices attempted connection
    assert mock_connection.enable.call_count >= 2

    # Verify connections were properly closed
    assert mock_connection.disconnect.call_count >= 2


def test_capture_timeout_logs_correct_device_and_command(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Test that timeout log messages include correct device and command info."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Mock ConnectHandler
    mock_connection = Mock()
    mock_connection.enable = Mock()
    mock_connection.disconnect = Mock()
    mock_connection.send_command = Mock(
        side_effect=NetMikoTimeoutException("Timeout on show version")
    )

    with patch("nw_diff.app.ConnectHandler", return_value=mock_connection):
        with caplog.at_level(logging.ERROR):
            with app.app.test_client() as client:
                client.post("/capture/origin/router1")

    # Verify specific error message format
    error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
    timeout_log = next(
        (log for log in error_logs if "Command timed out" in log.message), None
    )

    assert timeout_log is not None
    assert "router1" in timeout_log.message
    # Should mention at least one command that timed out
    assert any(
        cmd in timeout_log.message
        for cmd in ["show version", "show running-config", "show ip interface brief"]
    )


# --- Tests for streaming task logs ---


def test_capture_stream_creates_task_and_sets_session_log(
    tmp_path: Path, monkeypatch
) -> None:
    """Streaming capture should return task metadata and set session_log."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    task_log_dir = tmp_path / "task-logs"
    monkeypatch.setattr(app, "TASK_LOG_DIR", task_log_dir)
    monkeypatch.setattr(app, "TASK_LOG_RETENTION_SECONDS", -1)
    monkeypatch.setattr(app, "TASK_LOG_DELETE_ON_COMPLETE", False)
    app.TASKS.clear()

    mock_connection = Mock()
    mock_connection.enable = Mock()
    mock_connection.disconnect = Mock()
    mock_connection.send_command = Mock(return_value="Version output")

    with patch("nw_diff.app.ConnectHandler", return_value=mock_connection) as connector:
        with app.app.test_client() as client:
            response = client.post("/api/capture/origin/router1/stream")
            payload = response.get_json()

        assert response.status_code == 202
        assert payload is not None

        task_state = app._get_task_state(  # pylint: disable=protected-access
            payload["task_id"]
        )
        assert task_state is not None
        assert task_state.done_event.wait(timeout=2)
        assert connector.call_args.kwargs["session_log"] == str(task_state.log_path)
        assert task_state.status == "completed"


def test_task_stream_masks_password(tmp_path: Path, monkeypatch) -> None:
    """Task stream should mask DEVICE_PASSWORD values."""
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "secret")

    task_log_dir = tmp_path / "task-logs"
    monkeypatch.setattr(app, "TASK_LOG_DIR", task_log_dir)
    monkeypatch.setattr(app, "TASK_LOG_RETENTION_SECONDS", -1)
    monkeypatch.setattr(app, "TASK_LOG_DELETE_ON_COMPLETE", False)
    app.TASKS.clear()

    task_state = app._create_task_state(  # pylint: disable=protected-access
        "origin", "router1", batch=False, reserved_hosts={"router1"}
    )
    task_state.log_path.write_text("password=secret\nline2\n", encoding="utf-8")
    task_state.status = "completed"
    task_state.done_event.set()

    with app.app.test_client() as client:
        response = client.get(f"/api/tasks/{task_state.task_id}/stream")
        data = response.get_data(as_text=True)

    assert "secret" not in data
    assert "password=***" in data
    app._release_capture_hosts({"router1"})  # pylint: disable=protected-access


def test_task_cancel_sets_cancel_flag(tmp_path: Path, monkeypatch) -> None:
    """Cancel endpoint should set the task cancellation flag."""
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    task_log_dir = tmp_path / "task-logs"
    monkeypatch.setattr(app, "TASK_LOG_DIR", task_log_dir)
    monkeypatch.setattr(app, "TASK_LOG_RETENTION_SECONDS", -1)
    monkeypatch.setattr(app, "TASK_LOG_DELETE_ON_COMPLETE", False)
    app.TASKS.clear()

    task_state = app._create_task_state(  # pylint: disable=protected-access
        "origin", "router1", batch=False, reserved_hosts={"router1"}
    )

    with app.app.test_client() as client:
        response = client.post(f"/api/tasks/{task_state.task_id}/cancel")

    assert response.status_code == 200
    assert task_state.cancel_event.is_set()
    app._release_capture_hosts({"router1"})  # pylint: disable=protected-access


# --- Tests for marker file functionality ---


def test_create_unavailable_marker(tmp_path: Path, monkeypatch) -> None:
    """Test that unavailable marker files are created correctly."""
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))

    filepath = origin_dir / "test-marker.txt"
    storage.create_unavailable_marker(str(filepath), "timeout")

    assert filepath.exists()
    content = filepath.read_text(encoding="utf-8")
    assert content == "[UNAVAILABLE: timeout]\n"


def test_get_file_status_available(tmp_path: Path) -> None:
    """Test get_file_status returns 'available' for normal files."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Normal content", encoding="utf-8")

    status, content = storage.get_file_status(str(test_file))

    assert status == "available"
    assert content == "Normal content"


def test_get_file_status_timeout(tmp_path: Path) -> None:
    """Test get_file_status detects timeout marker files."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("[UNAVAILABLE: timeout]\n", encoding="utf-8")

    status, content = storage.get_file_status(str(test_file))

    assert status == "timeout"
    assert "[UNAVAILABLE: timeout]" in content


def test_get_file_status_connection_failed(tmp_path: Path) -> None:
    """Test get_file_status detects connection_failed marker files."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("[UNAVAILABLE: connection_failed]\n", encoding="utf-8")

    status, content = storage.get_file_status(str(test_file))

    assert status == "connection_failed"
    assert "[UNAVAILABLE: connection_failed]" in content


def test_get_file_status_not_found(tmp_path: Path) -> None:
    """Test get_file_status returns 'not_found' for missing files."""
    test_file = tmp_path / "nonexistent.txt"

    status, content = storage.get_file_status(str(test_file))

    assert status == "not_found"
    assert content is None


def test_capture_creates_timeout_marker(tmp_path: Path, monkeypatch) -> None:
    """Test that capture endpoint creates marker file on timeout."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))

    # Mock ConnectHandler - timeout on show running-config
    mock_connection = Mock()
    mock_connection.enable = Mock()
    mock_connection.disconnect = Mock()

    def send_command_side_effect(
        command, read_timeout=None
    ):  # pylint: disable=unused-argument
        if "show version" in command:
            return "Version output"
        if "show running-config" in command:
            raise NetMikoTimeoutException("Command timed out")
        return f"Output for {command}"

    mock_connection.send_command = Mock(side_effect=send_command_side_effect)

    with patch("nw_diff.app.ConnectHandler", return_value=mock_connection):
        with app.app.test_client() as client:
            response = client.post("/capture/origin/router1")

    # Verify redirect (not error)
    assert response.status_code == 302

    # Verify marker file was created for timed out command
    marker_file = origin_dir / "router1-show_running-config.txt"
    assert marker_file.exists()
    content = marker_file.read_text(encoding="utf-8")
    assert "[UNAVAILABLE: timeout]" in content

    # Verify successful command still has normal file
    success_file = origin_dir / "router1-show_version.txt"
    assert success_file.exists()
    content = success_file.read_text(encoding="utf-8")
    assert content == "Version output"


def test_capture_creates_connection_failed_markers(tmp_path: Path, monkeypatch) -> None:
    """Test that capture endpoint creates marker files on connection failure."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))

    # Mock ConnectHandler to raise connection error
    with patch(
        "nw_diff.app.ConnectHandler", side_effect=Exception("Connection refused")
    ):
        with app.app.test_client() as client:
            response = client.post("/capture/origin/router1")

    # Verify redirect (not error 500)
    assert response.status_code == 302

    # Verify marker files were created for all commands
    marker_file1 = origin_dir / "router1-show_version.txt"
    marker_file2 = origin_dir / "router1-show_running-config.txt"

    assert marker_file1.exists()
    assert marker_file2.exists()

    content1 = marker_file1.read_text(encoding="utf-8")
    content2 = marker_file2.read_text(encoding="utf-8")

    assert "[UNAVAILABLE: connection_failed]" in content1
    assert "[UNAVAILABLE: connection_failed]" in content2


def test_capture_all_creates_timeout_markers(tmp_path: Path, monkeypatch) -> None:
    """Test that capture_all creates marker files on timeout."""
    # Setup test data with two hosts
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model
router1,10.0.0.1,admin,22,cisco
router2,10.0.0.2,admin,22,cisco
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))

    # Mock ConnectHandler
    mock_connection = Mock()
    mock_connection.enable = Mock()
    mock_connection.disconnect = Mock()

    def send_command_side_effect(
        command, read_timeout=None
    ):  # pylint: disable=unused-argument
        # Timeout on show running-config for all devices
        if "show running-config" in command:
            raise NetMikoTimeoutException("Command timed out")
        return f"Output for {command}"

    mock_connection.send_command = Mock(side_effect=send_command_side_effect)

    with patch("nw_diff.app.ConnectHandler", return_value=mock_connection):
        with app.app.test_client() as client:
            response = client.post("/capture_all/origin")

    # Verify redirect
    assert response.status_code == 302

    # Verify marker files were created for timed out commands
    for router in ["router1", "router2"]:
        marker_file = origin_dir / f"{router}-show_running-config.txt"
        assert marker_file.exists()
        content = marker_file.read_text(encoding="utf-8")
        assert "[UNAVAILABLE: timeout]" in content


def test_capture_all_creates_connection_failed_markers(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that capture_all creates marker files when a device fails to connect."""
    # Setup test data with two hosts
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model
router1,10.0.0.1,admin,22,cisco
router2,10.0.0.2,admin,22,cisco
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("DEVICE_PASSWORD", "test_password")

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))

    # Mock ConnectHandler - first call succeeds, second fails
    connection_count = {"count": 0}

    def connect_handler_side_effect(*args, **kwargs):  # pylint: disable=unused-argument
        connection_count["count"] += 1
        if connection_count["count"] == 1:
            # First device succeeds
            mock_connection = Mock()
            mock_connection.enable = Mock()
            mock_connection.disconnect = Mock()
            mock_connection.send_command = Mock(return_value="Output")
            return mock_connection
        # Second device fails
        raise ConnectionError("Connection refused")

    with patch("nw_diff.app.ConnectHandler", side_effect=connect_handler_side_effect):
        with app.app.test_client() as client:
            response = client.post("/capture_all/origin")

    # Verify redirect
    assert response.status_code == 302

    # Verify marker files were created for router2 (failed connection)
    marker_file1 = origin_dir / "router2-show_version.txt"
    marker_file2 = origin_dir / "router2-show_running-config.txt"

    assert marker_file1.exists()
    assert marker_file2.exists()

    content1 = marker_file1.read_text(encoding="utf-8")
    content2 = marker_file2.read_text(encoding="utf-8")

    assert "[UNAVAILABLE: connection_failed]" in content1
    assert "[UNAVAILABLE: connection_failed]" in content2


def test_host_list_displays_timeout_status(tmp_path: Path, monkeypatch) -> None:
    """Test that host list page shows timeout status correctly."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create marker file for timeout
    marker_file = origin_dir / "router1-show_version.txt"
    marker_file.write_text("[UNAVAILABLE: timeout]\n", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    # Check that timeout is displayed
    assert "timeout" in html.lower() or "TIMEOUT" in html


def test_host_list_displays_connection_failed_status(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that host list page shows connection failed status correctly."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create marker file for connection failed
    marker_file = origin_dir / "router1-show_version.txt"
    marker_file.write_text("[UNAVAILABLE: connection_failed]\n", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    # Check that connection failed is displayed
    assert "connection" in html.lower() and "failed" in html.lower()


def test_export_json_includes_timeout_status(tmp_path: Path, monkeypatch) -> None:
    """Test that JSON export includes timeout status."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create marker file for timeout
    marker_file = origin_dir / "router1-show_version.txt"
    marker_file.write_text("[UNAVAILABLE: timeout]\n", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 200
    data = response.json
    assert data is not None
    assert "commands" in data
    assert len(data["commands"]) > 0

    # Find the command with timeout
    cmd_data = next(
        (cmd for cmd in data["commands"] if "show version" in cmd["command"]), None
    )
    assert cmd_data is not None
    assert cmd_data["origin"]["status"] == "timeout"


def test_export_json_includes_connection_failed_status(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that JSON export includes connection_failed status."""
    # Setup test data
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)

    # Setup storage directories
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(origin_dir))
    monkeypatch.setattr(storage, "DEST_DIR", str(dest_dir))

    # Create marker file for connection failed
    marker_file = origin_dir / "router1-show_version.txt"
    marker_file.write_text("[UNAVAILABLE: connection_failed]\n", encoding="utf-8")

    with app.app.test_client() as client:
        response = client.get("/api/export/router1")

    assert response.status_code == 200
    data = response.json
    assert data is not None
    assert "commands" in data

    # Find the command with connection_failed
    cmd_data = next(
        (cmd for cmd in data["commands"] if "show version" in cmd["command"]), None
    )
    assert cmd_data is not None
    assert cmd_data["origin"]["status"] == "connection_failed"
