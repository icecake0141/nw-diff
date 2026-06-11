"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.

SQLite-backed task repository for v2 capture jobs.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional, TypedDict

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureTaskStatus

_DB_INIT_LOCK = threading.Lock()


class TaskRecord(TypedDict):
    """Repository representation of a capture task row."""

    task_id: str
    status: str
    mode: str
    base: str
    hosts: list[str]
    requested_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    cancel_requested: bool
    error: Optional[str]
    result: Optional[dict[str, Any]]


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


def init_db() -> None:
    """Initialize DB schema once."""
    with _DB_INIT_LOCK:
        with _connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capture_tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    base TEXT NOT NULL,
                    hosts_json TEXT NOT NULL,
                    requested_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    result_json TEXT
                )
                """
            )
            conn.commit()


def create_task(task_id: str, mode: str, base: str, hosts: list[str]) -> None:
    """Create a new queued capture task."""
    init_db()
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO capture_tasks
            (id, status, mode, base, hosts_json, requested_at, cancel_requested)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                task_id,
                CaptureTaskStatus.QUEUED.value,
                mode,
                base,
                json.dumps(hosts),
                now,
            ),
        )
        conn.commit()


def update_task(
    task_id: str,
    *,
    status: Optional[CaptureTaskStatus] = None,
    started_at: Optional[float] = None,
    finished_at: Optional[float] = None,
    error: Optional[str] = None,
    result: Optional[dict[str, Any]] = None,
) -> None:
    """Update mutable task fields."""
    init_db()
    fields: list[str] = []
    values: list[Any] = []

    if status is not None:
        fields.append("status = ?")
        values.append(status.value)
    if started_at is not None:
        fields.append("started_at = ?")
        values.append(started_at)
    if finished_at is not None:
        fields.append("finished_at = ?")
        values.append(finished_at)
    if error is not None:
        fields.append("error = ?")
        values.append(error)
    if result is not None:
        fields.append("result_json = ?")
        values.append(json.dumps(result))

    if not fields:
        return

    values.append(task_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE capture_tasks SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        conn.commit()


def get_task(task_id: str) -> Optional[TaskRecord]:
    """Fetch one task by id."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM capture_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_task(row)


def request_cancel(task_id: str) -> bool:
    """Mark queued/running task as cancel requested."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE capture_tasks
            SET cancel_requested = 1
            WHERE id = ?
              AND status IN (?, ?)
            """,
            (
                task_id,
                CaptureTaskStatus.QUEUED.value,
                CaptureTaskStatus.RUNNING.value,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def is_cancel_requested(task_id: str) -> bool:
    """Return whether cancellation has been requested for task."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT cancel_requested FROM capture_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        return False
    return bool(row[0])


def list_tasks(
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    host_contains: str | None = None,
) -> list[TaskRecord]:
    """Return recent tasks, optionally filtered by status."""
    init_db()
    clauses: list[str] = []
    params: list[Any] = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if host_contains:
        clauses.append("hosts_json LIKE ?")
        params.append(f"%{host_contains}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        "SELECT * FROM capture_tasks "
        f"{where} "
        "ORDER BY requested_at DESC "
        "LIMIT ? OFFSET ?"
    )
    params.append(max(1, min(limit, 500)))
    params.append(max(0, offset))

    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, tuple(params)).fetchall()

    return [_row_to_task(row) for row in rows]


def claim_next_queued_task() -> Optional[TaskRecord]:
    """Atomically claim the oldest queued task and mark it as running."""
    init_db()
    started_at = time.time()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM capture_tasks
            WHERE status = ?
            ORDER BY requested_at ASC
            LIMIT 1
            """,
            (CaptureTaskStatus.QUEUED.value,),
        ).fetchone()
        if row is None:
            conn.rollback()
            return None

        conn.execute(
            """
            UPDATE capture_tasks
            SET status = ?, started_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                CaptureTaskStatus.RUNNING.value,
                started_at,
                row["id"],
                CaptureTaskStatus.QUEUED.value,
            ),
        )
        updated = conn.execute(
            "SELECT * FROM capture_tasks WHERE id = ?",
            (row["id"],),
        ).fetchone()
        conn.commit()
        if updated is None:
            return None
        return _row_to_task(updated)


def recover_orphaned_running_tasks() -> list[TaskRecord]:
    """
    Mark tasks stuck in running state as failed.

    Returns the recovered tasks so caller can perform side effects
    such as releasing host locks.
    """
    init_db()
    finished_at = time.time()
    error = "Recovered after process restart while task was running"
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT * FROM capture_tasks WHERE status = ?",
            (CaptureTaskStatus.RUNNING.value,),
        ).fetchall()
        if not rows:
            conn.rollback()
            return []

        conn.execute(
            """
            UPDATE capture_tasks
            SET status = ?, finished_at = ?, error = ?
            WHERE status = ?
            """,
            (
                CaptureTaskStatus.FAILED.value,
                finished_at,
                error,
                CaptureTaskStatus.RUNNING.value,
            ),
        )
        conn.commit()

    return [_row_to_task(row) for row in rows]


def count_tasks_by_status() -> dict[str, int]:
    """Return counts grouped by task status."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM capture_tasks
            GROUP BY status
            """).fetchall()
    counts: dict[str, int] = {}
    for status, cnt in rows:
        counts[str(status)] = int(cnt)
    return counts


def get_latest_task_for_host(host: str) -> Optional[TaskRecord]:
    """Return latest task containing the target host."""
    init_db()
    needle = f'"{host}"'
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM capture_tasks
            WHERE hosts_json LIKE ?
            ORDER BY requested_at DESC
            LIMIT 1
            """,
            (f"%{needle}%",),
        ).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def _load_hosts_json(value: str) -> list[str]:
    hosts = json.loads(value)
    if not isinstance(hosts, list):
        return []
    return [str(host) for host in hosts]


def _row_to_task(row: sqlite3.Row) -> TaskRecord:
    return {
        "task_id": row["id"],
        "status": row["status"],
        "mode": row["mode"],
        "base": row["base"],
        "hosts": _load_hosts_json(row["hosts_json"]),
        "requested_at": row["requested_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "cancel_requested": bool(row["cancel_requested"]),
        "error": row["error"],
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
    }
