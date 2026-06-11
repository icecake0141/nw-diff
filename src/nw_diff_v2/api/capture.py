"""Capture API endpoints (v2 scaffold)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff_v2.domain.models import (
    CaptureRequest,
    CaptureTaskResponse,
)
from nw_diff_v2.domain.services.capture_queue_service import (
    CaptureConflictError,
    CaptureRequestError,
    queue_capture_request,
)
from nw_diff_v2.security.auth import require_auth

router = APIRouter(prefix="/api/v2/captures", tags=["v2-captures"])


@router.post("", response_model=CaptureTaskResponse)
def start_capture(
    request: CaptureRequest, _: None = Depends(require_auth)
) -> CaptureTaskResponse:
    """Start a capture task."""
    try:
        task_id, task_status, conflicts = queue_capture_request(
            mode=request.mode,
            base=request.base,
            requested_hosts=request.hosts,
        )
    except CaptureRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CaptureConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return CaptureTaskResponse(task_id=task_id, status=task_status, conflicts=conflicts)
