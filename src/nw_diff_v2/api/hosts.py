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

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff_v2.api.error_messages import ERR_INVALID_HOSTNAME, ERR_INVALID_VIEW
from nw_diff_v2.domain.services.host_diff_service import (
    HostArtifactsNotFoundError,
    build_host_detail,
    build_host_summary,
)
from nw_diff_v2.security.auth import require_auth
from nw_diff_v2.security.validation import validate_hostname

router = APIRouter(prefix="/api/v2/hosts", tags=["v2-hosts"])


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

    safe_status = status_filter.strip().lower()
    allowed_status_filters = {"", "changed", "identical", "unavailable", "not_found"}
    if safe_status not in allowed_status_filters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status_filter",
        )

    safe_command_contains = command_contains.strip().lower()
    try:
        return build_host_detail(
            hostname=hostname,
            view=safe_view,
            diff_mode=safe_diff_mode,
            context_lines=context_lines,
            status_filter=safe_status,
            command_contains=safe_command_contains,
        )
    except HostArtifactsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No artifacts found for host: {exc}",
        ) from exc


@router.get("/summary")
def host_summary(
    _: None = Depends(require_auth),
    limit: int = 200,
    host_contains: str = "",
    prioritize_failed: bool = True,
) -> dict:
    """Return per-host diff summary sorted by changed count desc."""
    return build_host_summary(
        limit=limit,
        host_contains=host_contains,
        prioritize_failed=prioritize_failed,
    )
