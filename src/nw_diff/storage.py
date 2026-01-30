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

import datetime
import logging
import os

from .security import validate_hostname, validate_command, validate_base_directory

logger = logging.getLogger("nw-diff")

# Directory settings
ORIGIN_DIR = "origin"
DEST_DIR = "dest"
DIFF_DIR = "diff"
BACKUP_DIR = "backup"


def _ensure_directories():
    """Create required directories if they do not exist."""
    os.makedirs(ORIGIN_DIR, exist_ok=True)
    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(DIFF_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


# Create directories on module import for backward compatibility
_ensure_directories()


def get_backup_filename(filepath):
    """
    Generates a backup filename with timestamp.
    Format: YYYYMMDD_HHMMSS_hostname-command.txt
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(filepath)
    return os.path.join(BACKUP_DIR, f"{timestamp}_{filename}")


def rotate_backups(filepath):
    """
    Keeps only the last 10 backups for a given file.
    Deletes older backups beyond the 10 most recent.
    """
    if not os.path.exists(BACKUP_DIR):
        return

    filename = os.path.basename(filepath)
    # Find all backups for this file
    backup_files = []
    for backup_file in os.listdir(BACKUP_DIR):
        if backup_file.endswith(f"_{filename}"):
            backup_path = os.path.join(BACKUP_DIR, backup_file)
            backup_files.append((backup_path, os.path.getmtime(backup_path)))

    # Sort by modification time (newest first)
    backup_files.sort(key=lambda x: x[1], reverse=True)

    # Keep only the 10 most recent, delete the rest
    for backup_path, _ in backup_files[10:]:
        try:
            os.remove(backup_path)
        except OSError:
            pass


def create_backup(filepath):
    """
    Creates a backup of the file before it is overwritten.
    Only creates backup if the file exists.
    After backup creation, rotates backups to keep only the last 10.
    """
    if os.path.exists(filepath):
        backup_path = get_backup_filename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as src:
                content = src.read()
            with open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(content)
            rotate_backups(filepath)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to create backup for %s: %s", filepath, exc)


def get_file_path(host, command, base):
    """
    base: "origin" or "dest"
    Constructs the filename using the host and command
    (spaces replaced with underscores).
    Validates inputs to prevent path traversal attacks.
    """
    # Validate inputs
    if not validate_hostname(host):
        raise ValueError(f"Invalid hostname: {host}")
    if not validate_command(command):
        raise ValueError(f"Invalid command: {command}")
    if not validate_base_directory(base):
        raise ValueError(f"Invalid base directory: {base}")

    # Construct filename
    safe_command = command.replace(" ", "_")
    filename = f"{host}-{safe_command}.txt"

    # Get base directory path
    if base == "origin":
        base_dir = ORIGIN_DIR
    else:  # base == "dest" (already validated)
        base_dir = DEST_DIR

    # Construct full path and normalize it
    full_path = os.path.join(base_dir, filename)
    normalized_path = os.path.normpath(full_path)

    # Verify the normalized path is still within the intended base directory
    base_abs = os.path.abspath(base_dir)
    path_abs = os.path.abspath(normalized_path)

    if not path_abs.startswith(base_abs + os.sep) and path_abs != base_abs:
        logger.error(
            "Path traversal attempt detected: %s escapes %s", path_abs, base_abs
        )
        raise ValueError("Path traversal detected")

    return normalized_path


def get_diff_file_path(host, command):
    """
    Constructs the path for the diff file.
    Validates inputs to prevent path traversal attacks.
    """
    # Validate inputs
    if not validate_hostname(host):
        raise ValueError(f"Invalid hostname: {host}")
    if not validate_command(command):
        raise ValueError(f"Invalid command: {command}")

    # Construct filename
    safe_command = command.replace(" ", "_")
    filename = f"{host}-{safe_command}-diff.html"

    # Construct full path and normalize it
    full_path = os.path.join(DIFF_DIR, filename)
    normalized_path = os.path.normpath(full_path)

    # Verify the normalized path is still within the diff directory
    diff_abs = os.path.abspath(DIFF_DIR)
    path_abs = os.path.abspath(normalized_path)

    if not path_abs.startswith(diff_abs + os.sep) and path_abs != diff_abs:
        logger.error(
            "Path traversal attempt detected: %s escapes %s", path_abs, diff_abs
        )
        raise ValueError("Path traversal detected")

    return normalized_path


def get_file_mtime(filepath):
    """
    Returns the modification time of the file in a formatted string,
    or 'file not found' if the file does not exist.
    """
    if os.path.exists(filepath):
        return datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    return "file not found"


def create_unavailable_marker(filepath, reason):
    """
    Creates a marker file indicating the command output is unavailable.
    
    Args:
        filepath: Path where the marker file should be created
        reason: Reason for unavailability ('timeout', 'connection_failed', etc.)
    
    The marker file contains a special format that can be detected when reading.
    """
    marker_content = f"[UNAVAILABLE: {reason}]\n"
    try:
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(marker_content)
        logger.debug("Created unavailable marker: %s (reason: %s)", filepath, reason)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to create unavailable marker for %s: %s", filepath, exc)


def get_file_status(filepath):
    """
    Returns the status of a file.
    
    Returns:
        tuple: (status, content) where status is one of:
            - 'available': Normal file with content
            - 'timeout': Command timed out
            - 'connection_failed': Could not connect to device
            - 'unavailable': Other unavailability reason
            - 'not_found': File does not exist
    """
    if not os.path.exists(filepath):
        return ('not_found', None)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's a marker file
        if content.startswith('[UNAVAILABLE:'):
            # Extract reason from marker
            match = content.split('[UNAVAILABLE:')
            if len(match) > 1:
                reason = match[1].split(']')[0].strip()
                return (reason, content)
            return ('unavailable', content)
        
        return ('available', content)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Error reading file %s: %s", filepath, exc)
        return ('error', None)
