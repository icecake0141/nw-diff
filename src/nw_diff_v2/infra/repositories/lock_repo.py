"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.

SQLite-backed host lock repository for cross-process capture locking.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from nw_diff_v2.config import settings

_DB_INIT_LOCK = threading.Lock()


def _db_path() -> Path:
    db_url = settings.db_url
    if not db_url.startswith("sqlite:///"):
        raise RuntimeError("Only sqlite:/// DB URLs are supported in v2 scaffold")
    return Path(db_url.replace("sqlite:///", "", 1))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


def init_lock_table() -> None:
    """Ensure host lock table exists."""
    with _DB_INIT_LOCK:
        with _connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS host_locks (
                    host TEXT PRIMARY KEY,
                    acquired_at REAL NOT NULL
                )
                """)
            conn.commit()


def try_lock_hosts(hosts: set[str], *, timeout_seconds: float) -> tuple[bool, set[str]]:
    """Try to lock all hosts atomically; return conflicts when busy."""
    normalized = sorted({host for host in hosts if host})
    if not normalized:
        return True, set()

    init_lock_table()
    now = time.time()
    timeout = max(0.0, float(timeout_seconds))

    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")

        if timeout > 0:
            conn.execute(
                "DELETE FROM host_locks WHERE acquired_at < ?",
                (now - timeout,),
            )

        placeholders = ",".join("?" for _ in normalized)
        rows = conn.execute(
            f"SELECT host FROM host_locks WHERE host IN ({placeholders})",
            tuple(normalized),
        ).fetchall()
        conflicts = {str(row["host"]) for row in rows}
        if conflicts:
            conn.rollback()
            return False, conflicts

        conn.executemany(
            "INSERT INTO host_locks (host, acquired_at) VALUES (?, ?)",
            [(host, now) for host in normalized],
        )
        conn.commit()

    return True, set()


def release_hosts(hosts: set[str]) -> None:
    """Release host locks."""
    normalized = sorted({host for host in hosts if host})
    if not normalized:
        return

    init_lock_table()
    placeholders = ",".join("?" for _ in normalized)
    with _connect() as conn:
        conn.execute(
            f"DELETE FROM host_locks WHERE host IN ({placeholders})",
            tuple(normalized),
        )
        conn.commit()


def list_locks() -> list[dict[str, float | str]]:
    """Return current lock rows."""
    init_lock_table()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT host, acquired_at FROM host_locks ORDER BY host ASC"
        ).fetchall()
    return [
        {
            "host": str(row["host"]),
            "acquired_at": float(row["acquired_at"]),
        }
        for row in rows
    ]


def cleanup_stale_locks(*, timeout_seconds: float) -> int:
    """Delete stale lock rows and return deleted count."""
    timeout = max(0.0, float(timeout_seconds))
    if timeout <= 0:
        return 0
    init_lock_table()
    cutoff = time.time() - timeout
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM host_locks WHERE acquired_at < ?",
            (cutoff,),
        )
        conn.commit()
        return int(cur.rowcount)


def force_set_lock(host: str, acquired_at: float) -> None:
    """Testing helper to upsert a lock row with a specific timestamp."""
    init_lock_table()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO host_locks (host, acquired_at) VALUES (?, ?)",
            (host, acquired_at),
        )
        conn.commit()
