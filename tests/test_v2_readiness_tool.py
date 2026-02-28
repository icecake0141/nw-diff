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


def _write_readiness(path: Path, *, status: str) -> None:
    payload = {
        "status": status,
        "checks": [{"name": "queue_depth", "ok": status == "ok", "detail": ""}],
        "counts": {"queued": 0, "running": 0},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_check_v2_readiness_ok(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    _write_readiness(readiness, status="ok")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-readiness.py",
            "--input-file",
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "status=ok" in result.stdout


def test_check_v2_readiness_degraded_fail_and_allow(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    _write_readiness(readiness, status="degraded")

    failed = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-readiness.py",
            "--input-file",
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 1

    allowed = subprocess.run(
        [
            sys.executable,
            "scripts/check-v2-readiness.py",
            "--input-file",
            str(readiness),
            "--allow-degraded",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert allowed.returncode == 0
