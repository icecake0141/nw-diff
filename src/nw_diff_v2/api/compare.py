"""Diff/compare API endpoints for v2 artifacts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff_v2.api.error_messages import ERR_INVALID_HOSTNAME, ERR_INVALID_VIEW
from nw_diff_v2.domain.models import CompareFilesRequest
from nw_diff_v2.domain.services.compare_service import (
    CompareNotFoundError,
    CompareRequestError,
    build_compare_files_payload,
    build_diff_host_payload,
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

    view = request.view.lower()
    if view not in {"inline", "sidebyside"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_VIEW,
        )
    try:
        return build_compare_files_payload(
            host1=request.host1,
            host2=request.host2,
            base=request.base,
            command=request.command,
            view=view,
        )
    except CompareRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CompareNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


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

    try:
        return build_diff_host_payload(hostname=hostname, view=safe_view)
    except CompareNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
