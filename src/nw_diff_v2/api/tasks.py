"""Task status/cancel API endpoints for v2 captures."""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from nw_diff_v2.api.error_messages import ERR_INVALID_TASK_ID, ERR_TASK_NOT_FOUND
from nw_diff_v2.domain.models import (
    CaptureBase,
    CaptureTaskDetail,
    CaptureTaskResponse,
    CaptureTaskStatus,
    CaptureTaskSummary,
)
from nw_diff_v2.domain.services.capture_service import launch_capture_task
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.task_repo import (
    create_task,
    get_task,
    list_tasks,
    request_cancel,
)
from nw_diff_v2.infra.storage.task_logs import task_log_path
from nw_diff_v2.config import settings
from nw_diff_v2.security.auth import require_auth

router = APIRouter(prefix="/api/v2/tasks", tags=["v2-tasks"])
_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _ensure_valid_task_id(task_id: str) -> None:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERR_INVALID_TASK_ID,
        )


@router.get("", response_model=list[CaptureTaskSummary])
def task_list(
    _: None = Depends(require_auth),
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    host_contains: Optional[str] = None,
    running_only: bool = False,
) -> list[CaptureTaskSummary]:
    """List recent tasks with optional status filter."""
    status_value = (
        "running"
        if running_only
        else (status_filter.lower() if status_filter else None)
    )
    host_value = host_contains.strip() if host_contains else None
    tasks = list_tasks(
        limit=limit,
        offset=offset,
        status=status_value,
        host_contains=host_value,
    )
    return [
        CaptureTaskSummary(
            task_id=task["task_id"],
            status=task["status"],
            mode=task["mode"],
            base=task["base"],
            hosts=task["hosts"],
            requested_at=task["requested_at"],
            started_at=task["started_at"],
            finished_at=task["finished_at"],
            cancel_requested=task["cancel_requested"],
        )
        for task in tasks
    ]


@router.get("/{task_id}", response_model=CaptureTaskDetail)
def task_status(task_id: str, _: None = Depends(require_auth)) -> CaptureTaskDetail:
    """Return task status by id."""
    _ensure_valid_task_id(task_id)
    task = get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERR_TASK_NOT_FOUND
        )
    return CaptureTaskDetail(
        task_id=task["task_id"],
        status=task["status"],
        mode=task["mode"],
        base=task["base"],
        hosts=task["hosts"],
        requested_at=task["requested_at"],
        started_at=task["started_at"],
        finished_at=task["finished_at"],
        cancel_requested=task["cancel_requested"],
        error=task["error"],
        result=task["result"],
    )


@router.post("/{task_id}/cancel", response_model=CaptureTaskDetail)
def task_cancel(task_id: str, _: None = Depends(require_auth)) -> CaptureTaskDetail:
    """Request cancellation for a running task."""
    _ensure_valid_task_id(task_id)
    updated = request_cancel(task_id)
    if not updated:
        task = get_task(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=ERR_TASK_NOT_FOUND
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already {task['status']}",
        )
    task = get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERR_TASK_NOT_FOUND
        )
    return CaptureTaskDetail(
        task_id=task["task_id"],
        status=task["status"],
        mode=task["mode"],
        base=task["base"],
        hosts=task["hosts"],
        requested_at=task["requested_at"],
        started_at=task["started_at"],
        finished_at=task["finished_at"],
        cancel_requested=task["cancel_requested"],
        error=task["error"],
        result=task["result"],
    )


@router.post("/{task_id}/retry", response_model=CaptureTaskResponse)
def task_retry(task_id: str, _: None = Depends(require_auth)) -> CaptureTaskResponse:
    """Create a new queued task from terminal task parameters."""
    _ensure_valid_task_id(task_id)
    task = get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERR_TASK_NOT_FOUND
        )
    if task["status"] in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is still {task['status']}",
        )

    target_hosts = set(task["hosts"])
    host_rows = load_hosts(settings.hosts_csv)
    host_map = {row.host: row.model_dump() for row in host_rows}
    unknown_hosts = sorted(target_hosts.difference(host_map.keys()))
    if unknown_hosts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown host(s): {', '.join(unknown_hosts)}",
        )

    acquired, conflicts = try_lock_hosts(target_hosts)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Capture already running: {', '.join(sorted(conflicts))}",
        )

    new_task_id = uuid.uuid4().hex
    target_host_rows = [host_map[host] for host in sorted(target_hosts)]
    try:
        create_task(
            task_id=new_task_id,
            mode=task["mode"],
            base=task["base"],
            hosts=sorted(target_hosts),
        )
        launch_capture_task(
            task_id=new_task_id,
            base=CaptureBase(task["base"]),
            hosts=target_host_rows,
            reserved_hosts=target_hosts,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        release_hosts(target_hosts)
        raise

    return CaptureTaskResponse(
        task_id=new_task_id,
        status=CaptureTaskStatus.QUEUED,
        conflicts=[],
    )


@router.get("/{task_id}/stream")
def task_stream(
    task_id: str,
    _: None = Depends(require_auth),
    tail_lines: int = 0,
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Stream task log via server-sent events."""
    _ensure_valid_task_id(task_id)
    if get_task(task_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERR_TASK_NOT_FOUND
        )

    log_path = task_log_path(task_id)
    log_path.touch(exist_ok=True)

    def _generate(tail_lines: int, last_event_id: Optional[str]):
        with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
            yield "retry: 3000\n\n"
            lines = log_file.readlines()
            next_event_id = len(lines)
            start_idx = 0
            if last_event_id is not None:
                try:
                    last_id = int(last_event_id)
                    start_idx = min(last_id + 1, len(lines))
                except ValueError:
                    start_idx = 0
            elif tail_lines > 0:
                start_idx = max(0, len(lines) - tail_lines)

            for idx, line in enumerate(lines[start_idx:], start=start_idx):
                yield f"id: {idx}\ndata: {line.rstrip()}\n\n"

            last_emit = time.time()

            while True:
                line = log_file.readline()
                if line:
                    yield f"id: {next_event_id}\ndata: {line.rstrip()}\n\n"
                    next_event_id += 1
                    last_emit = time.time()
                    continue
                task = get_task(task_id)
                if task is None:
                    yield "event: status\ndata: gone\n\n"
                    break
                if task["status"] in {"completed", "failed", "cancelled"}:
                    yield f"event: status\ndata: {task['status']}\n\n"
                    break
                if (time.time() - last_emit) >= settings.task_stream_heartbeat_seconds:
                    # SSE comment heartbeat keeps idle connections alive.
                    yield ": keepalive\n\n"
                    last_emit = time.time()
                time.sleep(settings.task_stream_sleep_seconds)

    safe_tail_lines = max(0, min(tail_lines, 500))
    return StreamingResponse(
        _generate(tail_lines=safe_tail_lines, last_event_id=last_event_id),
        media_type="text/event-stream",
    )
