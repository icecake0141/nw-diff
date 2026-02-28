"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _write_locks(path: Path, *, count: int, stale_count: int) -> None:
    locks = []
    for idx in range(count):
        locks.append(
            {
                "host": f"router{idx + 1}",
                "acquired_at": 1.0,
                "age_seconds": 10.0,
                "is_stale": idx < stale_count,
            }
        )
    payload = {
        "count": count,
        "timeout_seconds": 3600,
        "locks": locks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_check_v2_locks_ok(tmp_path: Path) -> None:
    src = tmp_path / "locks.json"
    _write_locks(src, count=1, stale_count=0)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-locks.py",
            "--input-file",
            str(src),
            "--max-locks",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "locks count=1 stale=0 max_locks=2" in result.stdout


def test_check_v2_locks_fails_by_max(tmp_path: Path) -> None:
    src = tmp_path / "locks.json"
    _write_locks(src, count=3, stale_count=0)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-locks.py",
            "--input-file",
            str(src),
            "--max-locks",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "count=3 exceeds max_locks=2" in result.stdout


def test_check_v2_locks_stale_allow_switch(tmp_path: Path) -> None:
    src = tmp_path / "locks.json"
    _write_locks(src, count=1, stale_count=1)

    failed = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-locks.py",
            "--input-file",
            str(src),
            "--max-locks",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 1
    assert "stale locks detected: 1" in failed.stdout

    allowed = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-locks.py",
            "--input-file",
            str(src),
            "--max-locks",
            "2",
            "--allow-stale",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert allowed.returncode == 0


def test_check_v2_locks_summary_output(tmp_path: Path) -> None:
    src = tmp_path / "locks.json"
    summary = tmp_path / "summary.md"
    _write_locks(src, count=2, stale_count=1)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-locks.py",
            "--input-file",
            str(src),
            "--max-locks",
            "1",
            "--summary-path",
            str(summary),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    text = summary.read_text(encoding="utf-8")
    assert "## V2 Locks" in text
    assert "- status: **failed**" in text
    assert "count=2 exceeds max_locks=1" in text
