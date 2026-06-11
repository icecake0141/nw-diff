"""Export API endpoints for v2 artifacts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from nw_diff_v2.api.error_messages import ERR_INVALID_HOSTNAME
from nw_diff_v2.domain.services.export_service import (
    ExportNotFoundError,
    build_host_diff_export_json,
    build_host_export_json,
    render_host_export_html,
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

    try:
        return build_host_export_json(hostname)
    except ExportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{hostname}/diff-json")
def export_host_diff_json(hostname: str, _: None = Depends(require_auth)) -> dict:
    """Export per-command origin/dest status and diff summary as JSON."""
    if not validate_hostname(hostname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_HOSTNAME,
        )

    try:
        return build_host_diff_export_json(hostname)
    except ExportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{hostname}/html", response_class=HTMLResponse)
def export_host_html(hostname: str, _: None = Depends(require_auth)) -> HTMLResponse:
    """Export available v2 artifacts for the target host as HTML."""
    data = export_host_json(hostname, _)
    return HTMLResponse(content=render_host_export_html(hostname, data))
