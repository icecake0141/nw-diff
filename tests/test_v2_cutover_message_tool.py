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


def _write_eval(path: Path, *, go: bool, reasons: list[str]) -> None:
    payload = {
        "go": go,
        "readiness_status": "ok" if go else "degraded",
        "deploy_validation_status": "ok" if go else "failed",
        "has_contract_diff": not go,
        "counts": {
            "queued": 0,
            "running": 0,
            "failed": 0 if go else 1,
            "locked_hosts": 0,
        },
        "limits": {"max_queued": 0, "max_running": 5, "max_failed": 0, "max_locked": 0},
        "reasons": reasons,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_render_v2_cutover_message_markdown_and_summary(tmp_path: Path) -> None:
    src = tmp_path / "eval.json"
    out = tmp_path / "msg.md"
    summary = tmp_path / "summary.md"
    _write_eval(src, go=False, reasons=["contract diff has changes"])

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render-v2-cutover-message.py",
            "--input",
            str(src),
            "--format",
            "markdown",
            "--output",
            str(out),
            "--summary-path",
            str(summary),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "NO-GO" in text
    assert "contract diff has changes" in text
    assert "locked=0" in text
    assert summary.read_text(encoding="utf-8") == text


def test_render_v2_cutover_message_text(tmp_path: Path) -> None:
    src = tmp_path / "eval.json"
    out = tmp_path / "msg.txt"
    _write_eval(src, go=True, reasons=[])

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render-v2-cutover-message.py",
            "--input",
            str(src),
            "--format",
            "text",
            "--output",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "Cutover decision: GO" in text
