"""System and operations payload builders."""

from __future__ import annotations

import time
from typing import Any, Iterable

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services.lock_service import (
    cleanup_stale_locks,
    list_locks,
    release_hosts,
)
from nw_diff_v2.infra.repositories.task_repo import count_tasks_by_status, list_tasks

RouteKey = tuple[str, tuple[str, ...]]

REQUIRED_ROUTE_CONTRACT: set[RouteKey] = {
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


def collect_v2_route_set(routes: Iterable[Any]) -> set[RouteKey]:
    """Collect current /api/v2 route path/method pairs."""
    route_keys: set[RouteKey] = set()
    for route in routes:
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


def _route_items(route_keys: set[RouteKey]) -> list[dict[str, Any]]:
    return [
        {"path": path, "methods": list(methods)}
        for path, methods in sorted(
            route_keys, key=lambda row: (row[0], ",".join(row[1]))
        )
    ]


def build_worker_status() -> dict[str, Any]:
    """Return queue/worker-oriented status counters."""
    counts = count_tasks_by_status()
    lock_rows = list_locks()
    return {
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
        "cancelled": counts.get("cancelled", 0),
        "total": sum(counts.values()),
        "locked_hosts": len(lock_rows),
    }


def build_readiness(route_keys: set[RouteKey]) -> dict[str, Any]:
    """Return operational readiness combining queue load and contract sanity."""
    counts = count_tasks_by_status()
    lock_rows = list_locks()
    queued = int(counts.get("queued", 0))
    running = int(counts.get("running", 0))
    locked = int(len(lock_rows))

    missing = sorted(
        REQUIRED_ROUTE_CONTRACT.difference(route_keys),
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
        "missing_routes": _route_items(set(missing)),
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


def build_locks_payload() -> dict[str, Any]:
    """Return host lock rows for operational visibility."""
    now = time.time()
    timeout = max(0.0, float(settings.host_lock_timeout_seconds))
    owners = _running_task_host_owners()
    items = []
    for row in list_locks():
        host = str(row["host"])
        acquired_at = float(row["acquired_at"])
        age_seconds = max(0.0, now - acquired_at)
        is_stale = 0.0 < timeout < age_seconds
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


def cleanup_locks_payload() -> dict[str, Any]:
    """Delete stale locks based on configured timeout and return a summary."""
    deleted = cleanup_stale_locks()
    remaining = list_locks()
    return {
        "deleted": int(deleted),
        "remaining": int(len(remaining)),
        "timeout_seconds": max(0.0, float(settings.host_lock_timeout_seconds)),
    }


def release_locks_payload(hosts: list[str]) -> dict[str, Any]:
    """Force-release specified hosts from lock table and return release details."""
    existing = {str(row["host"]) for row in list_locks()}
    released = sorted([host for host in hosts if host in existing])
    not_locked = sorted([host for host in hosts if host not in existing])
    if released:
        release_hosts(set(released))
    return {
        "released": released,
        "not_locked": not_locked,
        "remaining": int(len(list_locks())),
    }


def build_routes_payload(route_keys: set[RouteKey]) -> dict[str, Any]:
    """Return current v2 route surface for compatibility checks."""
    items = [
        {**item, "name": ""}
        for item in _route_items(route_keys)
    ]
    return {"count": len(items), "routes": items}


def build_contract_payload(route_keys: set[RouteKey]) -> dict[str, Any]:
    """Check required v2 API contract against actual registered routes."""
    missing = sorted(
        REQUIRED_ROUTE_CONTRACT.difference(route_keys),
        key=lambda row: (row[0], ",".join(row[1])),
    )
    extra = sorted(
        route_keys.difference(REQUIRED_ROUTE_CONTRACT),
        key=lambda row: (row[0], ",".join(row[1])),
    )
    return {
        "status": "ok" if not missing else "missing",
        "required_count": len(REQUIRED_ROUTE_CONTRACT),
        "actual_count": len(route_keys),
        "missing": _route_items(set(missing)),
        "extra": _route_items(set(extra)),
    }
