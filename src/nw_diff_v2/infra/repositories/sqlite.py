"""Shared SQLite connection helpers for v2 repositories."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nw_diff_v2.config import settings

BUSY_TIMEOUT_MS = 3000


def db_path() -> Path:
    """Return the configured SQLite database path."""
    db_url = settings.db_url
    if not db_url.startswith("sqlite:///"):
        raise RuntimeError("Only sqlite:/// DB URLs are supported")
    return Path(db_url.replace("sqlite:///", "", 1))


def connect() -> sqlite3.Connection:
    """Open a SQLite connection with repository-wide defaults."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return conn
