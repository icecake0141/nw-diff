"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.

Host detail APIs for v2 UI/automation.
"""

from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff_v2.domain.services.diff_service import compute_diff, compute_diff_status
from nw_diff_v2.api.error_messages import ERR_INVALID_HOSTNAME, ERR_INVALID_VIEW
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.task_repo import get_latest_task_for_host
from nw_diff_v2.config import settings
from nw_diff_v2.infra.storage.files import (
    artifact_path_by_key,
    command_label_from_key,
    list_command_keys,
    read_output_by_key,
)
from nw_diff_v2.security.auth import require_auth
from nw_diff_v2.security.validation import validate_hostname

router = APIRouter(prefix="/api/v2/hosts", tags=["v2-hosts"])


def _result_category(diff_status: str) -> str:
    if diff_status == "changes detected":
        return "changed"
    if diff_status == "identical":
        return "identical"
    if diff_status == "file not found":
        return "not_found"
    return "unavailable"


@router.get("/{hostname}/detail")
def host_detail(  # pylint: disable=too-many-positional-arguments
    hostname: str,
    _: None = Depends(require_auth),
    view: str = "inline",
    diff_mode: str = "full",
    context_lines: int = 3,
    status_filter: str = "",
    command_contains: str = "",
) -> dict:
    """Return per-command origin/dest diff details for one host."""
    if not validate_hostname(hostname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_HOSTNAME,
        )
    safe_view = view.lower()
    if safe_view not in {"inline", "sidebyside"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_VIEW,
        )
    safe_diff_mode = diff_mode.strip().lower()
    if safe_diff_mode not in {"full", "context"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid diff_mode",
        )
    if context_lines < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context_lines",
        )

    command_keys = sorted(
        list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
    )
    if not command_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No artifacts found for host: {hostname}",
        )

    all_results: list[dict] = []

    for command_key in command_keys:
        origin_path = artifact_path_by_key("origin", hostname, command_key)
        dest_path = artifact_path_by_key("dest", hostname, command_key)
        origin_status, origin_data = read_output_by_key("origin", hostname, command_key)
        dest_status, dest_data = read_output_by_key("dest", hostname, command_key)

        origin_mtime = origin_path.stat().st_mtime if origin_path.exists() else None
        dest_mtime = dest_path.stat().st_mtime if dest_path.exists() else None

        if origin_status == "available" and dest_status == "available":
            diff_status, diff_html = compute_diff(
                origin_data or "",
                dest_data or "",
                safe_view,
                diff_mode=safe_diff_mode,
                context_lines=context_lines,
            )
        elif origin_status != "not_found":
            diff_status = f"origin {origin_status}"
            diff_html = (
                "<div class='alert alert-warning'>Origin data "
                f"{html.escape(origin_status)}</div>"
            )
        elif dest_status != "not_found":
            diff_status = f"dest {dest_status}"
            diff_html = (
                "<div class='alert alert-warning'>Destination data "
                f"{html.escape(dest_status)}</div>"
            )
        else:
            diff_status = "file not found"
            diff_html = ""

        all_results.append(
            {
                "command_key": command_key,
                "command": command_label_from_key(command_key),
                "origin_status": origin_status,
                "dest_status": dest_status,
                "origin_mtime": origin_mtime,
                "dest_mtime": dest_mtime,
                "diff_status": diff_status,
                "diff_html": diff_html,
            }
        )

    safe_status = status_filter.strip().lower()
    safe_command_contains = command_contains.strip().lower()
    allowed_status_filters = {"", "changed", "identical", "unavailable", "not_found"}
    if safe_status not in allowed_status_filters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status_filter",
        )

    results = all_results
    if safe_status:
        results = [
            item
            for item in results
            if _result_category(str(item["diff_status"])) == safe_status
        ]
    if safe_command_contains:
        results = [
            item
            for item in results
            if safe_command_contains in str(item["command"]).lower()
            or safe_command_contains in str(item["command_key"]).lower()
        ]

    changed = sum(
        1 for item in results if _result_category(str(item["diff_status"])) == "changed"
    )
    identical = sum(
        1
        for item in results
        if _result_category(str(item["diff_status"])) == "identical"
    )
    unavailable = sum(
        1
        for item in results
        if _result_category(str(item["diff_status"])) == "unavailable"
    )
    not_found = sum(
        1
        for item in results
        if _result_category(str(item["diff_status"])) == "not_found"
    )

    return {
        "hostname": hostname,
        "view": safe_view,
        "toggle_view": "sidebyside" if safe_view == "inline" else "inline",
        "diff_mode": safe_diff_mode,
        "context_lines": context_lines,
        "status_filter": safe_status,
        "command_contains": command_contains,
        "summary": {
            "total_before_filter": len(all_results),
            "total": len(results),
            "changed": changed,
            "identical": identical,
            "unavailable": unavailable,
            "not_found": not_found,
        },
        "command_results": results,
    }


@router.get("/summary")
def host_summary(
    _: None = Depends(require_auth),
    limit: int = 200,
    host_contains: str = "",
    prioritize_failed: bool = True,
) -> dict:
    """Return per-host diff summary sorted by changed count desc."""
    hosts = load_hosts(settings.hosts_csv)
    query = host_contains.strip().lower()
    rows: list[dict] = []

    for host in hosts:
        hostname = host.host
        if query and query not in hostname.lower():
            continue
        command_keys = sorted(
            list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
        )
        changed = 0
        identical = 0
        unavailable = 0
        not_found = 0

        for command_key in command_keys:
            origin_status, origin_data = read_output_by_key(
                "origin", hostname, command_key
            )
            dest_status, dest_data = read_output_by_key("dest", hostname, command_key)
            if origin_status == "available" and dest_status == "available":
                diff_status = compute_diff_status(origin_data or "", dest_data or "")
            elif origin_status != "not_found":
                diff_status = f"origin {origin_status}"
            elif dest_status != "not_found":
                diff_status = f"dest {dest_status}"
            else:
                diff_status = "file not found"
            category = _result_category(diff_status)
            if category == "changed":
                changed += 1
            elif category == "identical":
                identical += 1
            elif category == "unavailable":
                unavailable += 1
            else:
                not_found += 1

        rows.append(
            {
                "host": hostname,
                "ip": host.ip,
                "model": host.model,
                "total": len(command_keys),
                "changed": changed,
                "identical": identical,
                "unavailable": unavailable,
                "not_found": not_found,
                "last_capture_at": max(
                    (
                        path.stat().st_mtime
                        for base in ("origin", "dest")
                        for path in [
                            artifact_path_by_key(base, hostname, key)
                            for key in command_keys
                        ]
                        if path.exists()
                    ),
                    default=None,
                ),
                "last_task_status": None,
                "last_task_finished_at": None,
            }
        )

    for row in rows:
        latest = get_latest_task_for_host(str(row["host"]))
        if latest is not None:
            row["last_task_status"] = latest["status"]
            row["last_task_finished_at"] = latest["finished_at"]

    def _failed_priority(row: dict) -> int:
        if not prioritize_failed:
            return 1
        return (
            0 if str(row.get("last_task_status", "")) in {"failed", "cancelled"} else 1
        )

    rows.sort(
        key=lambda row: (
            _failed_priority(row),
            -int(row["changed"]),
            -int(row["unavailable"]),
            -(
                float(row["last_capture_at"])
                if row["last_capture_at"] is not None
                else -1.0
            ),
            str(row["host"]),
        )
    )
    safe_limit = max(1, min(limit, 1000))
    limited = rows[:safe_limit]
    return {
        "count": len(limited),
        "total_hosts": len(rows),
        "rows": limited,
    }
