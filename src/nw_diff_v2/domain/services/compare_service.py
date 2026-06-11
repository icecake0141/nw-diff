"""Compare payload builders for artifact APIs."""

from __future__ import annotations

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureBase
from nw_diff_v2.domain.services.diff_service import (
    compute_diff,
    compute_diff_status,
    generate_side_by_side_html,
)
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.storage.files import (
    artifact_path,
    command_label_from_key,
    list_command_keys,
    read_output_by_key,
)


class CompareRequestError(RuntimeError):
    """Raised when a compare request is invalid."""


class CompareNotFoundError(RuntimeError):
    """Raised when required compare artifacts are missing."""


def _inventory_hosts() -> set[str]:
    return {row.host for row in load_hosts(settings.hosts_csv)}


def build_compare_files_payload(
    *,
    host1: str,
    host2: str,
    base: CaptureBase,
    command: str,
    view: str,
) -> dict:
    """Compare one command output between two hosts within the same base."""
    inventory_hosts = _inventory_hosts()
    invalid_hosts: list[str] = []
    if host1 not in inventory_hosts:
        invalid_hosts.append("Invalid host1: must exactly match an inventory host")
    if host2 not in inventory_hosts:
        invalid_hosts.append("Invalid host2: must exactly match an inventory host")
    if invalid_hosts:
        raise CompareRequestError(", ".join(invalid_hosts))

    if not command or not command.strip():
        raise CompareRequestError("Invalid command")

    path1 = artifact_path(base.value, host1, command)
    path2 = artifact_path(base.value, host2, command)
    if not path1.exists():
        raise CompareNotFoundError(f"File for {host1} not found")
    if not path2.exists():
        raise CompareNotFoundError(f"File for {host2} not found")

    data1 = path1.read_text(encoding="utf-8")
    data2 = path2.read_text(encoding="utf-8")
    if view == "sidebyside":
        diff_html = generate_side_by_side_html(data1, data2)
        diff_status = compute_diff_status(data1, data2)
    else:
        diff_status, diff_html = compute_diff(data1, data2, "inline")
    return {
        "host1": host1,
        "host2": host2,
        "base": base.value,
        "command": command,
        "view": view,
        "status": diff_status,
        "diff_html": diff_html,
    }


def build_diff_host_payload(*, hostname: str, view: str) -> dict:
    """Compare origin/dest outputs for all commands of one host."""
    command_keys = sorted(
        list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
    )
    if not command_keys:
        raise CompareNotFoundError(f"No artifacts found for host: {hostname}")

    commands: list[dict] = []
    for command_key in command_keys:
        origin_status, origin_data = read_output_by_key("origin", hostname, command_key)
        dest_status, dest_data = read_output_by_key("dest", hostname, command_key)
        diff_status = "unavailable"
        diff_html = ""
        if origin_status == "available" and dest_status == "available":
            if view == "sidebyside":
                diff_html = generate_side_by_side_html(
                    origin_data or "", dest_data or ""
                )
                diff_status = compute_diff_status(origin_data or "", dest_data or "")
            else:
                diff_status, diff_html = compute_diff(
                    origin_data or "", dest_data or "", "inline"
                )
        commands.append(
            {
                "command_key": command_key,
                "command": command_label_from_key(command_key),
                "origin_status": origin_status,
                "dest_status": dest_status,
                "diff_status": diff_status,
                "diff_html": diff_html,
            }
        )

    changed = sum(1 for item in commands if item["diff_status"] == "changes detected")
    identical = sum(1 for item in commands if item["diff_status"] == "identical")
    unavailable = len(commands) - changed - identical
    return {
        "hostname": hostname,
        "view": view,
        "summary": {
            "total": len(commands),
            "changed": changed,
            "identical": identical,
            "unavailable": unavailable,
        },
        "commands": commands,
    }
