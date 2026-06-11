"""System/operations endpoints for v2."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services.system_service import (
    build_contract_payload,
    build_locks_payload,
    build_readiness,
    build_routes_payload,
    build_worker_status,
    cleanup_locks_payload,
    collect_v2_route_set,
    release_locks_payload,
)
from nw_diff_v2.infra.repositories.task_repo import init_db
from nw_diff_v2.security.validation import validate_hostname
from nw_diff_v2.security.auth import require_auth

router = APIRouter(prefix="/api/v2/system", tags=["v2-system"])


class LockReleaseRequest(BaseModel):
    """Manual lock-release request payload."""

    hosts: list[str] = Field(default_factory=list)


@router.get("/worker")
def worker_status(_: None = Depends(require_auth)) -> dict:
    """Return queue/worker-oriented status counters."""
    return build_worker_status()


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
    return build_readiness(collect_v2_route_set(request.app.routes))


@router.get("/locks")
def locks(_: None = Depends(require_auth)) -> dict:
    """Return host lock rows for operational visibility."""
    return build_locks_payload()


@router.post("/locks/cleanup")
def locks_cleanup(_: None = Depends(require_auth)) -> dict:
    """Delete stale locks based on configured timeout."""
    return cleanup_locks_payload()


@router.post("/locks/release")
def locks_release(request: LockReleaseRequest, _: None = Depends(require_auth)) -> dict:
    """Force-release specified hosts from lock table."""
    normalized = sorted(
        {str(host).strip() for host in request.hosts if str(host).strip()}
    )
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
    return release_locks_payload(normalized)


@router.get("/routes")
def routes(request: Request, _: None = Depends(require_auth)) -> dict:
    """Return current v2 route surface for compatibility checks."""
    return build_routes_payload(collect_v2_route_set(request.app.routes))


@router.get("/contract")
def contract(request: Request, _: None = Depends(require_auth)) -> dict:
    """Check required v2 API contract against actual registered routes."""
    return build_contract_payload(collect_v2_route_set(request.app.routes))
