"""System/operations endpoints for v2."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from nw_diff_v2.infra.repositories.task_repo import (
    count_tasks_by_status,
    init_db,
    list_tasks,
)
from nw_diff_v2.config import settings
from nw_diff_v2.domain.services.lock_service import (
    cleanup_stale_locks,
    list_locks,
    release_hosts,
)
from nw_diff_v2.security.validation import validate_hostname
from nw_diff_v2.security.auth import require_auth

router = APIRouter(prefix="/api/v2/system", tags=["v2-system"])


class LockReleaseRequest(BaseModel):
    """Manual lock-release request payload."""

    hosts: list[str] = Field(default_factory=list)


_REQUIRED_ROUTE_CONTRACT: set[tuple[str, tuple[str, ...]]] = {
    ("/api/v2/captures", ("POST",)),
    ("/api/v2/tasks", ("GET",)),
    ("/api/v2/tasks/{task_id}", ("GET",)),
    ("/api/v2/tasks/{task_id}/cancel", ("POST",)),
    ("/api/v2/tasks/{task_id}/retry", ("POST",)),
    ("/api/v2/tasks/{task_id}/stream", ("GET",)),
    ("/api/v2/compare/files", ("POST",)),
    ("/api/v2/diff/{hostname}", ("GET",)),
    ("/api/v2/hosts/summary", ("GET",)),
    ("/api/v2/hosts/{hostname}/detail", ("GET",)),
    ("/api/v2/exports/{hostname}", ("GET",)),
    ("/api/v2/exports/{hostname}/diff-json", ("GET",)),
    ("/api/v2/exports/{hostname}/html", ("GET",)),
    ("/api/v2/logs", ("GET",)),
    ("/api/v2/system/worker", ("GET",)),
    ("/api/v2/system/health", ("GET",)),
    ("/api/v2/system/readiness", ("GET",)),
    ("/api/v2/system/locks", ("GET",)),
    ("/api/v2/system/locks/cleanup", ("POST",)),
    ("/api/v2/system/locks/release", ("POST",)),
    ("/api/v2/system/routes", ("GET",)),
    ("/api/v2/system/contract", ("GET",)),
}


def _running_task_host_owners() -> dict[str, list[str]]:
    """Map host -> running task ids for lock ownership hints."""
    owners: dict[str, list[str]] = {}
    rows = list_tasks(limit=500, offset=0, status="running")
    for task in rows:
        task_id = str(task.get("task_id", ""))
        for host in task.get("hosts", []):
            key = str(host)
            owners.setdefault(key, []).append(task_id)
    return owners


def _collect_v2_route_set(request: Request) -> set[tuple[str, tuple[str, ...]]]:
    route_keys: set[tuple[str, tuple[str, ...]]] = set()
    for route in request.app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/api/v2"):
            continue
        methods = tuple(
            sorted(
                method
                for method in getattr(route, "methods", set())
                if method not in {"HEAD", "OPTIONS"}
            )
        )
        route_keys.add((path, methods))
    return route_keys


@router.get("/worker")
def worker_status(_: None = Depends(require_auth)) -> dict:
    """Return queue/worker-oriented status counters."""
    counts = count_tasks_by_status()
    locks = list_locks()
    return {
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
        "cancelled": counts.get("cancelled", 0),
        "total": sum(counts.values()),
        "locked_hosts": len(locks),
    }


@router.get("/health")
def health(_: None = Depends(require_auth)) -> dict:
    """Readiness-style health check for API and storage."""
    init_db()
    return {
        "status": "ok",
        "timestamp": time.time(),
        "db_url": settings.db_url,
        "artifact_root": settings.artifact_root,
    }


@router.get("/readiness")
def readiness(request: Request, _: None = Depends(require_auth)) -> dict:
    """Operational readiness combining queue load and contract sanity."""
    init_db()
    counts = count_tasks_by_status()
    locks = list_locks()
    queued = int(counts.get("queued", 0))
    running = int(counts.get("running", 0))
    locked = int(len(locks))

    actual = _collect_v2_route_set(request)
    missing = sorted(
        _REQUIRED_ROUTE_CONTRACT.difference(actual),
        key=lambda row: (row[0], ",".join(row[1])),
    )
    contract_ok = len(missing) == 0

    checks = [
        {
            "name": "contract",
            "ok": contract_ok,
            "detail": f"missing={len(missing)}",
        },
        {
            "name": "queue_depth",
            "ok": queued <= int(settings.readiness_max_queued),
            "detail": f"queued={queued}, max={int(settings.readiness_max_queued)}",
        },
        {
            "name": "running_depth",
            "ok": running <= int(settings.readiness_max_running),
            "detail": f"running={running}, max={int(settings.readiness_max_running)}",
        },
        {
            "name": "lock_depth",
            "ok": locked <= int(settings.readiness_max_locked),
            "detail": f"locked={locked}, max={int(settings.readiness_max_locked)}",
        },
    ]
    ok = all(check["ok"] for check in checks)
    return {
        "status": "ok" if ok else "degraded",
        "timestamp": time.time(),
        "checks": checks,
        "counts": {
            "queued": queued,
            "running": running,
            "completed": int(counts.get("completed", 0)),
            "failed": int(counts.get("failed", 0)),
            "cancelled": int(counts.get("cancelled", 0)),
            "locked_hosts": locked,
            "total": int(sum(counts.values())),
        },
        "thresholds": {
            "readiness_max_queued": int(settings.readiness_max_queued),
            "readiness_max_running": int(settings.readiness_max_running),
            "readiness_max_locked": int(settings.readiness_max_locked),
        },
        "missing_routes": [
            {"path": path, "methods": list(methods)} for path, methods in missing
        ],
    }


@router.get("/locks")
def locks(_: None = Depends(require_auth)) -> dict:
    """Return host lock rows for operational visibility."""
    now = time.time()
    timeout = max(0.0, float(settings.host_lock_timeout_seconds))
    owners = _running_task_host_owners()
    rows = list_locks()
    items = []
    for row in rows:
        host = str(row["host"])
        acquired_at = float(row["acquired_at"])
        age_seconds = max(0.0, now - acquired_at)
        is_stale = timeout > 0 and age_seconds > timeout
        items.append(
            {
                "host": host,
                "acquired_at": acquired_at,
                "age_seconds": age_seconds,
                "is_stale": is_stale,
                "owner_task_ids": owners.get(host, []),
            }
        )
    return {
        "count": len(items),
        "timeout_seconds": timeout,
        "locks": items,
    }


@router.post("/locks/cleanup")
def locks_cleanup(_: None = Depends(require_auth)) -> dict:
    """Delete stale locks based on configured timeout."""
    deleted = cleanup_stale_locks()
    remaining = list_locks()
    return {
        "deleted": int(deleted),
        "remaining": int(len(remaining)),
        "timeout_seconds": max(0.0, float(settings.host_lock_timeout_seconds)),
    }


@router.post("/locks/release")
def locks_release(
    request: LockReleaseRequest, _: None = Depends(require_auth)
) -> dict:
    """Force-release specified hosts from lock table."""
    normalized = sorted({str(host).strip() for host in request.hosts if str(host).strip()})
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hosts is required",
        )
    invalid = [host for host in normalized if not validate_hostname(host)]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid host(s): {', '.join(sorted(invalid))}",
        )
    existing = {str(row["host"]) for row in list_locks()}
    released = sorted([host for host in normalized if host in existing])
    not_locked = sorted([host for host in normalized if host not in existing])
    if released:
        release_hosts(set(released))
    return {
        "released": released,
        "not_locked": not_locked,
        "remaining": int(len(list_locks())),
    }


@router.get("/routes")
def routes(request: Request, _: None = Depends(require_auth)) -> dict:
    """Return current v2 route surface for compatibility checks."""
    items: list[dict] = []
    for path, methods in sorted(_collect_v2_route_set(request), key=lambda row: (row[0], ",".join(row[1]))):
        items.append(
            {
                "path": path,
                "methods": list(methods),
                "name": "",
            }
        )
    return {"count": len(items), "routes": items}


@router.get("/contract")
def contract(request: Request, _: None = Depends(require_auth)) -> dict:
    """Check required v2 API contract against actual registered routes."""
    actual = _collect_v2_route_set(request)
    missing = sorted(_REQUIRED_ROUTE_CONTRACT.difference(actual), key=lambda row: (row[0], ",".join(row[1])))
    extra = sorted(actual.difference(_REQUIRED_ROUTE_CONTRACT), key=lambda row: (row[0], ",".join(row[1])))
    return {
        "status": "ok" if not missing else "missing",
        "required_count": len(_REQUIRED_ROUTE_CONTRACT),
        "actual_count": len(actual),
        "missing": [{"path": path, "methods": list(methods)} for path, methods in missing],
        "extra": [{"path": path, "methods": list(methods)} for path, methods in extra],
    }
