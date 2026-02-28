"""Export API endpoints for v2 artifacts."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from nw_diff.diff import compute_diff_status
from nw_diff_v2.api.error_messages import ERR_INVALID_HOSTNAME
from nw_diff_v2.config import settings
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.storage.files import (
    command_label_from_key,
    list_command_keys,
    read_output_by_key,
)
from nw_diff_v2.security.auth import require_auth
from nw_diff_v2.security.validation import validate_hostname

router = APIRouter(prefix="/api/v2/exports", tags=["v2-exports"])


@router.get("/{hostname}")
def export_host_json(hostname: str, _: None = Depends(require_auth)) -> dict:
    """Export available v2 artifacts for the target host as JSON."""
    if not validate_hostname(hostname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_HOSTNAME,
        )

    root = Path(settings.artifact_root)
    if not root.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No artifacts"
        )

    result: dict[str, Any] = {"hostname": hostname, "bases": {"origin": [], "dest": []}}
    for base in ("origin", "dest"):
        base_dir = root / base
        if not base_dir.exists():
            continue
        for path in sorted(base_dir.glob(f"{hostname}-*.txt")):
            result["bases"][base].append(
                {
                    "file": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "modified_at": path.stat().st_mtime,
                }
            )

    if not result["bases"]["origin"] and not result["bases"]["dest"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No artifacts found for host: {hostname}",
        )
    return result


@router.get("/{hostname}/diff-json")
def export_host_diff_json(hostname: str, _: None = Depends(require_auth)) -> dict:
    """Export per-command origin/dest status and diff summary as JSON."""
    if not validate_hostname(hostname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_HOSTNAME,
        )

    hosts = load_hosts(settings.hosts_csv)
    host_row = next((row for row in hosts if row.host == hostname), None)
    if host_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hostname not found in hosts configuration",
        )

    command_keys = sorted(
        list_command_keys("origin", hostname) | list_command_keys("dest", hostname)
    )
    if not command_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No artifacts found for host: {hostname}",
        )

    commands: list[dict] = []
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


@router.get("/{hostname}/html", response_class=HTMLResponse)
def export_host_html(hostname: str, _: None = Depends(require_auth)) -> HTMLResponse:
    """Export available v2 artifacts for the target host as HTML."""
    data = export_host_json(hostname, _)
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
    return HTMLResponse(content="\n".join(html_parts))
