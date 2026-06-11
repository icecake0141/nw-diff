"""Capture task queue creation workflows."""

from __future__ import annotations

import uuid
from typing import Any

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureBase, CaptureMode, CaptureTaskStatus
from nw_diff_v2.domain.services.capture_service import launch_capture_task
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.task_repo import TaskRecord, create_task


class CaptureRequestError(RuntimeError):
    """Raised when a capture queue request is invalid."""


class CaptureConflictError(RuntimeError):
    """Raised when a capture queue request conflicts with active locks."""


def _load_host_map() -> dict[str, dict[str, Any]]:
    host_rows = load_hosts(settings.hosts_csv)
    return {row.host: row.model_dump() for row in host_rows}


def _create_queued_task(
    *,
    mode: str,
    base: str,
    target_hosts: set[str],
    host_map: dict[str, dict[str, Any]],
) -> str:
    task_id = uuid.uuid4().hex
    target_host_rows = [host_map[host] for host in sorted(target_hosts)]
    try:
        create_task(
            task_id=task_id,
            mode=mode,
            base=base,
            hosts=sorted(target_hosts),
        )
        launch_capture_task(
            task_id=task_id,
            base=CaptureBase(base),
            hosts=target_host_rows,
            reserved_hosts=target_hosts,
        )
    except Exception:
        release_hosts(target_hosts)
        raise
    return task_id


def queue_capture_request(
    *,
    mode: CaptureMode,
    base: CaptureBase,
    requested_hosts: list[str],
) -> tuple[str, CaptureTaskStatus, list[str]]:
    """Validate a capture request, reserve hosts, and enqueue a capture task."""
    host_map = _load_host_map()
    configured_hosts = set(host_map.keys())
    if mode == CaptureMode.BATCH:
        target_hosts = set(requested_hosts) if requested_hosts else configured_hosts
    else:
        if len(requested_hosts) != 1:
            raise CaptureRequestError("single mode requires exactly one host")
        target_hosts = set(requested_hosts)

    if not target_hosts:
        raise CaptureRequestError("No target hosts")

    unknown_hosts = sorted(target_hosts.difference(configured_hosts))
    if unknown_hosts:
        raise CaptureRequestError(f"Unknown host(s): {', '.join(unknown_hosts)}")

    acquired, conflicts = try_lock_hosts(target_hosts)
    current_conflicts = set(conflicts)
    skipped_conflicts = sorted(current_conflicts)
    if not acquired:
        policy = settings.batch_conflict_policy.lower()
        if mode == CaptureMode.BATCH and policy == "skip_locked":
            target_hosts = target_hosts.difference(conflicts)
            if not target_hosts:
                raise CaptureConflictError("All target hosts are currently locked")
            acquired, retry_conflicts = try_lock_hosts(target_hosts)
            current_conflicts = set(retry_conflicts)
        if not acquired:
            raise CaptureConflictError(
                "Capture already running: " + ", ".join(sorted(current_conflicts))
            )

    task_id = _create_queued_task(
        mode=mode.value,
        base=base.value,
        target_hosts=target_hosts,
        host_map=host_map,
    )
    conflicts_payload = skipped_conflicts if mode == CaptureMode.BATCH else []
    return task_id, CaptureTaskStatus.QUEUED, conflicts_payload


def queue_retry_request(task: TaskRecord) -> tuple[str, CaptureTaskStatus, list[str]]:
    """Create a new queued task from terminal task parameters."""
    target_hosts = set(task["hosts"])
    host_map = _load_host_map()
    unknown_hosts = sorted(target_hosts.difference(host_map.keys()))
    if unknown_hosts:
        raise CaptureRequestError(f"Unknown host(s): {', '.join(unknown_hosts)}")

    acquired, conflicts = try_lock_hosts(target_hosts)
    if not acquired:
        raise CaptureConflictError(
            f"Capture already running: {', '.join(sorted(conflicts))}"
        )

    task_id = _create_queued_task(
        mode=task["mode"],
        base=task["base"],
        target_hosts=target_hosts,
        host_map=host_map,
    )
    return task_id, CaptureTaskStatus.QUEUED, []
