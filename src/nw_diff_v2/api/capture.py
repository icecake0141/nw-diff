"""Capture API endpoints (v2 scaffold)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import (
    CaptureMode,
    CaptureRequest,
    CaptureTaskResponse,
    CaptureTaskStatus,
)
from nw_diff_v2.domain.services.capture_service import launch_capture_task
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.task_repo import create_task
from nw_diff_v2.security.auth import require_auth

router = APIRouter(prefix="/api/v2/captures", tags=["v2-captures"])


@router.post("", response_model=CaptureTaskResponse)
def start_capture(
    request: CaptureRequest, _: None = Depends(require_auth)
) -> CaptureTaskResponse:
    """Start a capture task."""
    host_rows = load_hosts(settings.hosts_csv)
    host_map = {row.host: row.model_dump() for row in host_rows}
    configured_hosts = set(host_map.keys())
    if request.mode == CaptureMode.BATCH:
        target_hosts = set(request.hosts) if request.hosts else configured_hosts
    else:
        if len(request.hosts) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="single mode requires exactly one host",
            )
        target_hosts = set(request.hosts)

    if not target_hosts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target hosts",
        )

    unknown_hosts = sorted(target_hosts.difference(configured_hosts))
    if unknown_hosts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown host(s): {', '.join(unknown_hosts)}",
        )

    acquired, conflicts = try_lock_hosts(target_hosts)
    current_conflicts = set(conflicts)
    skipped_conflicts = sorted(current_conflicts)
    if not acquired:
        policy = settings.batch_conflict_policy.lower()
        if request.mode == CaptureMode.BATCH and policy == "skip_locked":
            target_hosts = target_hosts.difference(conflicts)
            if not target_hosts:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="All target hosts are currently locked",
                )
            acquired, retry_conflicts = try_lock_hosts(target_hosts)
            current_conflicts = set(retry_conflicts)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Capture already running: "
                    + ", ".join(sorted(current_conflicts))
                ),
            )

    task_id = uuid.uuid4().hex
    target_host_rows = [host_map[host] for host in sorted(target_hosts)]
    try:
        create_task(
            task_id=task_id,
            mode=request.mode.value,
            base=request.base.value,
            hosts=sorted(target_hosts),
        )
        launch_capture_task(
            task_id=task_id,
            base=request.base,
            hosts=target_host_rows,
            reserved_hosts=target_hosts,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        release_hosts(target_hosts)
        raise
    return CaptureTaskResponse(
        task_id=task_id,
        status=CaptureTaskStatus.QUEUED,
        conflicts=skipped_conflicts if request.mode == CaptureMode.BATCH else [],
    )
