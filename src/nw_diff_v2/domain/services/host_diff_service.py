"""Host diff detail and summary builders."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services.diff_service import compute_diff, compute_diff_status
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.task_repo import (
    get_latest_task_for_host,
    list_tasks,
)
from nw_diff_v2.infra.storage.files import (
    artifact_path_by_key,
    command_label_from_key,
    list_command_keys,
    read_output_by_key,
)


class HostArtifactsNotFoundError(RuntimeError):
    """Raised when a host has no origin or destination artifacts."""


def result_category(diff_status: str) -> str:
    """Return the API summary category for a diff status."""
    if diff_status == "changes detected":
        return "changed"
    if diff_status == "identical":
        return "identical"
    if diff_status == "file not found":
        return "not_found"
    return "unavailable"


def _running_host_base_pairs() -> set[tuple[str, str]]:
    """Return (host, base) pairs currently in running task rows."""
    pairs: set[tuple[str, str]] = set()
    running_rows = list_tasks(limit=500, offset=0, status="running")
    for row in running_rows:
        base = str(row.get("base", "")).strip().lower()
        if base not in {"origin", "dest"}:
            continue
        for host in row.get("hosts", []):
            host_name = str(host).strip()
            if host_name:
                pairs.add((host_name, base))
    return pairs


def _capture_status_entry(path: Path, *, running: bool) -> dict[str, Any]:
    """Build captured/running/not_captured status payload for one artifact."""
    if path.exists():
        return {
            "status": "captured",
            "captured_at": path.stat().st_mtime,
        }
    if running:
        return {
            "status": "running",
            "captured_at": None,
        }
    return {
        "status": "not_captured",
        "captured_at": None,
    }


def _diff_payload_for_command(
    hostname: str,
    command_key: str,
    *,
    view: str,
    diff_mode: str,
    context_lines: int,
) -> dict[str, Any]:
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
            view,
            diff_mode=diff_mode,
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

    return {
        "command_key": command_key,
        "command": command_label_from_key(command_key),
        "origin_status": origin_status,
        "dest_status": dest_status,
        "origin_mtime": origin_mtime,
        "dest_mtime": dest_mtime,
        "diff_status": diff_status,
        "diff_html": diff_html,
    }


def build_host_detail(
    *,
    hostname: str,
    view: str,
    diff_mode: str,
    context_lines: int,
    status_filter: str,
    command_contains: str,
) -> dict[str, Any]:
    """Return per-command origin/dest diff details for one host."""
    command_keys = sorted(
        list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
    )
    if not command_keys:
        raise HostArtifactsNotFoundError(hostname)

    all_results = [
        _diff_payload_for_command(
            hostname,
            command_key,
            view=view,
            diff_mode=diff_mode,
            context_lines=context_lines,
        )
        for command_key in command_keys
    ]

    results = all_results
    if status_filter:
        results = [
            item
            for item in results
            if result_category(str(item["diff_status"])) == status_filter
        ]
    if command_contains:
        results = [
            item
            for item in results
            if command_contains in str(item["command"]).lower()
            or command_contains in str(item["command_key"]).lower()
        ]

    summary = {
        "total_before_filter": len(all_results),
        "total": len(results),
        "changed": sum(
            1
            for item in results
            if result_category(str(item["diff_status"])) == "changed"
        ),
        "identical": sum(
            1
            for item in results
            if result_category(str(item["diff_status"])) == "identical"
        ),
        "unavailable": sum(
            1
            for item in results
            if result_category(str(item["diff_status"])) == "unavailable"
        ),
        "not_found": sum(
            1
            for item in results
            if result_category(str(item["diff_status"])) == "not_found"
        ),
    }

    return {
        "hostname": hostname,
        "view": view,
        "toggle_view": "sidebyside" if view == "inline" else "inline",
        "diff_mode": diff_mode,
        "context_lines": context_lines,
        "status_filter": status_filter,
        "command_contains": command_contains,
        "summary": summary,
        "command_results": results,
    }


def _diff_status_for_command(hostname: str, command_key: str) -> str:
    origin_status, origin_data = read_output_by_key("origin", hostname, command_key)
    dest_status, dest_data = read_output_by_key("dest", hostname, command_key)
    if origin_status == "available" and dest_status == "available":
        return compute_diff_status(origin_data or "", dest_data or "")
    if origin_status != "not_found":
        return f"origin {origin_status}"
    if dest_status != "not_found":
        return f"dest {dest_status}"
    return "file not found"


def build_host_summary(
    *,
    limit: int,
    host_contains: str,
    prioritize_failed: bool,
) -> dict[str, Any]:
    """Return per-host diff summary sorted by changed count desc."""
    hosts = load_hosts(settings.hosts_csv)
    query = host_contains.strip().lower()
    running_pairs = _running_host_base_pairs()
    rows: list[dict[str, Any]] = []

    for host in hosts:
        hostname = host.host
        if query and query not in hostname.lower():
            continue
        command_keys = sorted(
            list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
        )
        counts = {"changed": 0, "identical": 0, "unavailable": 0, "not_found": 0}
        commands: list[dict[str, Any]] = []

        for command_key in command_keys:
            category = result_category(_diff_status_for_command(hostname, command_key))
            counts[category] += 1
            origin_path = artifact_path_by_key("origin", hostname, command_key)
            dest_path = artifact_path_by_key("dest", hostname, command_key)
            commands.append(
                {
                    "command_key": command_key,
                    "command": command_label_from_key(command_key),
                    "origin": _capture_status_entry(
                        origin_path, running=(hostname, "origin") in running_pairs
                    ),
                    "dest": _capture_status_entry(
                        dest_path, running=(hostname, "dest") in running_pairs
                    ),
                }
            )

        rows.append(
            {
                "host": hostname,
                "ip": host.ip,
                "model": host.model,
                "total": len(command_keys),
                **counts,
                "last_capture_at": max(
                    (
                        entry[base]["captured_at"]
                        for entry in commands
                        for base in ("origin", "dest")
                        if entry[base]["captured_at"] is not None
                    ),
                    default=None,
                ),
                "last_task_status": None,
                "last_task_finished_at": None,
                "commands": commands,
            }
        )

    for row in rows:
        latest = get_latest_task_for_host(str(row["host"]))
        if latest is not None:
            row["last_task_status"] = latest["status"]
            row["last_task_finished_at"] = latest["finished_at"]

    def _failed_priority(row: dict[str, Any]) -> int:
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
