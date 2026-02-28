"""Diff/compare API endpoints for v2 artifacts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff.diff import compute_diff, compute_diff_status, generate_side_by_side_html
from nw_diff_v2.api.error_messages import ERR_INVALID_HOSTNAME, ERR_INVALID_VIEW
from nw_diff_v2.domain.models import CompareFilesRequest
from nw_diff_v2.infra.storage.files import (
    artifact_path,
    command_label_from_key,
    list_command_keys,
    read_output_by_key,
)
from nw_diff_v2.security.auth import require_auth
from nw_diff_v2.security.validation import validate_hostname

router = APIRouter(prefix="/api/v2", tags=["v2-compare"])


@router.post("/compare/files")
def compare_files(
    request: CompareFilesRequest, _: None = Depends(require_auth)
) -> dict:
    """Compare one command output between two hosts within the same base."""
    if not validate_hostname(request.host1) or not validate_hostname(request.host2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_HOSTNAME,
        )
    if not request.command or any(
        token in request.command for token in ("..", "/", "\\")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid command",
        )

    view = request.view.lower()
    if view not in {"inline", "sidebyside"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_VIEW,
        )

    path1 = artifact_path(request.base.value, request.host1, request.command)
    path2 = artifact_path(request.base.value, request.host2, request.command)
    if not path1.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File for {request.host1} not found",
        )
    if not path2.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File for {request.host2} not found",
        )

    data1 = path1.read_text(encoding="utf-8")
    data2 = path2.read_text(encoding="utf-8")
    if view == "sidebyside":
        diff_html = generate_side_by_side_html(data1, data2)
        diff_status = compute_diff_status(data1, data2)
    else:
        diff_status, diff_html = compute_diff(data1, data2, "inline")
    return {
        "host1": request.host1,
        "host2": request.host2,
        "base": request.base.value,
        "command": request.command,
        "view": view,
        "status": diff_status,
        "diff_html": diff_html,
    }


@router.get("/diff/{hostname}")
def diff_host(
    hostname: str, _: None = Depends(require_auth), view: str = "inline"
) -> dict:
    """Compare origin/dest outputs for all commands of one host."""
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
        diff_status = "unavailable"
        diff_html = ""
        if origin_status == "available" and dest_status == "available":
            if safe_view == "sidebyside":
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
        "view": safe_view,
        "summary": {
            "total": len(commands),
            "changed": changed,
            "identical": identical,
            "unavailable": unavailable,
        },
        "commands": commands,
    }
