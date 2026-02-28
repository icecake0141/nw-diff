"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import json
from pathlib import Path
import subprocess
import sys


def _write_contract(path: Path, *, required: list[dict], actual: list[dict]) -> None:
    payload = {
        "schema_version": 1,
        "required_routes": required,
        "actual_routes": actual,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_diff_v2_contract_json_output_no_diff(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    out_json = tmp_path / "diff.json"

    routes = [
        {"path": "/api/v2/tasks", "methods": ["GET"]},
        {"path": "/api/v2/captures", "methods": ["POST"]},
    ]
    _write_contract(baseline, required=routes, actual=routes)
    _write_contract(candidate, required=routes, actual=routes)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/diff-v2-contract.py",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--json-output",
            str(out_json),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["has_diff"] is False
    assert payload["actual_added"] == []
    assert payload["required_removed"] == []


def test_diff_v2_contract_fail_on_diff(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"

    _write_contract(
        baseline,
        required=[{"path": "/api/v2/tasks", "methods": ["GET"]}],
        actual=[{"path": "/api/v2/tasks", "methods": ["GET"]}],
    )
    _write_contract(
        candidate,
        required=[
            {"path": "/api/v2/tasks", "methods": ["GET"]},
            {"path": "/api/v2/extra", "methods": ["GET"]},
        ],
        actual=[{"path": "/api/v2/tasks", "methods": ["GET"]}],
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/diff-v2-contract.py",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--fail-on-diff",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "required added: 1" in result.stdout
