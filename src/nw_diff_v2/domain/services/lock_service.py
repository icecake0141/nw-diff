"""Host-level locking for capture concurrency control."""

from __future__ import annotations

from nw_diff_v2.config import settings
from nw_diff_v2.infra.repositories.lock_repo import (
    cleanup_stale_locks as _cleanup_stale_locks,
    list_locks as _list_locks,
    release_hosts as _release_hosts,
    try_lock_hosts as _try_lock_hosts,
)


def _lock_timeout_seconds() -> float:
    return max(0.0, float(settings.host_lock_timeout_seconds))


def try_lock_hosts(hosts: set[str]) -> tuple[bool, set[str]]:
    """
    Try to reserve hosts for capture.

    Returns:
        (True, set()) on success.
        (False, {conflicts}) when one or more hosts are already active.
    """
    return _try_lock_hosts(hosts, timeout_seconds=_lock_timeout_seconds())


def release_hosts(hosts: set[str]) -> None:
    """Release previously reserved hosts."""
    _release_hosts(hosts)


def list_locks() -> list[dict[str, float | str]]:
    """List currently reserved hosts."""
    return _list_locks()


def cleanup_stale_locks() -> int:
    """Delete stale host locks using configured timeout."""
    return _cleanup_stale_locks(timeout_seconds=_lock_timeout_seconds())
