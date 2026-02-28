"""Logs API endpoints for v2 operations."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff_v2.api.error_messages import ERR_INVALID_TASK_ID
from nw_diff_v2.config import settings
from nw_diff_v2.infra.storage.task_logs import task_log_path
from nw_diff_v2.security.auth import require_auth

router = APIRouter(prefix="/api/v2/logs", tags=["v2-logs"])

_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


@router.get("")
def get_logs(
    _: None = Depends(require_auth),
    source: str = "app",
    level: str = "",
    contains: str = "",
    limit: int = 1000,
    tail: bool = True,
    task_id: str = "",
) -> dict:
    """Return app/task logs with optional filtering."""
    safe_limit = max(1, min(limit, 10000))
    source_value = source.lower()
    contains_value = contains.strip()
    lines: list[str] = []

    if source_value == "app":
        log_path = Path(settings.app_log_path)
        if log_path.exists():
            all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = all_lines[-safe_limit:] if tail else all_lines[:safe_limit]
            level_filter = level.upper().strip()
            if level_filter:
                lines = [line for line in selected if level_filter in line]
            else:
                lines = selected
            if contains_value:
                lines = [line for line in lines if contains_value in line]
        return {
            "source": "app",
            "path": str(log_path),
            "count": len(lines),
            "lines": lines,
        }

    if source_value == "task":
        if not task_id or not _TASK_ID_RE.match(task_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERR_INVALID_TASK_ID,
            )
        path = task_log_path(task_id)
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task log not found",
            )
        all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = all_lines[-safe_limit:] if tail else all_lines[:safe_limit]
        if contains_value:
            lines = [line for line in lines if contains_value in line]
        return {
            "source": "task",
            "task_id": task_id,
            "path": str(path),
            "count": len(lines),
            "lines": lines,
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid source",
    )
