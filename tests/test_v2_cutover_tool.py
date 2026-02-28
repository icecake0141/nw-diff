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


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_evaluate_v2_cutover_go(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    contract_diff = tmp_path / "contract_diff.json"

    _write_json(
        readiness,
        {
            "status": "ok",
            "counts": {"queued": 0, "running": 0, "failed": 0, "locked_hosts": 0},
            "checks": [],
        },
    )
    _write_json(contract_diff, {"has_diff": False})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate-v2-cutover.py",
            "--readiness-file",
            str(readiness),
            "--contract-diff-file",
            str(contract_diff),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["go"] is True


def test_evaluate_v2_cutover_no_go(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    contract_diff = tmp_path / "contract_diff.json"

    _write_json(
        readiness,
        {
            "status": "degraded",
            "counts": {"queued": 2, "running": 0, "failed": 1, "locked_hosts": 0},
            "checks": [],
        },
    )
    _write_json(contract_diff, {"has_diff": True})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate-v2-cutover.py",
            "--readiness-file",
            str(readiness),
            "--contract-diff-file",
            str(contract_diff),
            "--max-queued",
            "0",
            "--max-failed",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["go"] is False
    assert len(payload["reasons"]) >= 2


def test_evaluate_v2_cutover_uses_env_thresholds(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    contract_diff = tmp_path / "contract_diff.json"

    _write_json(
        readiness,
        {
            "status": "ok",
            "counts": {"queued": 2, "running": 1, "failed": 0, "locked_hosts": 1},
            "checks": [],
        },
    )
    _write_json(contract_diff, {"has_diff": False})

    env = {
        "V2_CUTOVER_MAX_QUEUED": "2",
        "V2_CUTOVER_MAX_RUNNING": "1",
        "V2_CUTOVER_MAX_FAILED": "0",
        "V2_CUTOVER_MAX_LOCKED": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate-v2-cutover.py",
            "--readiness-file",
            str(readiness),
            "--contract-diff-file",
            str(contract_diff),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**env},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["go"] is True
    assert payload["limits"]["max_queued"] == 2
    assert payload["limits"]["max_running"] == 1
    assert payload["limits"]["max_locked"] == 1
    assert payload["counts"]["locked_hosts"] == 1


def test_evaluate_v2_cutover_deploy_validation_gate(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    contract_diff = tmp_path / "contract_diff.json"
    deploy_validation = tmp_path / "deploy_validation.json"

    _write_json(
        readiness,
        {
            "status": "ok",
            "counts": {"queued": 0, "running": 0, "failed": 0, "locked_hosts": 0},
            "checks": [],
        },
    )
    _write_json(contract_diff, {"has_diff": False})
    _write_json(deploy_validation, {"status": "failed"})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate-v2-cutover.py",
            "--readiness-file",
            str(readiness),
            "--contract-diff-file",
            str(contract_diff),
            "--deploy-validation-file",
            str(deploy_validation),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["go"] is False
    assert payload["deploy_validation_status"] == "failed"


def test_evaluate_v2_cutover_no_go_by_locked_hosts(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    contract_diff = tmp_path / "contract_diff.json"

    _write_json(
        readiness,
        {
            "status": "ok",
            "counts": {"queued": 0, "running": 0, "failed": 0, "locked_hosts": 2},
            "checks": [],
        },
    )
    _write_json(contract_diff, {"has_diff": False})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate-v2-cutover.py",
            "--readiness-file",
            str(readiness),
            "--contract-diff-file",
            str(contract_diff),
            "--max-locked",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["go"] is False
    assert any(
        "locked_hosts=2 exceeds max_locked=0" in reason for reason in payload["reasons"]
    )


def test_evaluate_v2_cutover_summary_includes_locked(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    contract_diff = tmp_path / "contract_diff.json"
    summary = tmp_path / "summary.md"

    _write_json(
        readiness,
        {
            "status": "ok",
            "counts": {"queued": 0, "running": 0, "failed": 0, "locked_hosts": 1},
            "checks": [],
        },
    )
    _write_json(contract_diff, {"has_diff": False})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate-v2-cutover.py",
            "--readiness-file",
            str(readiness),
            "--contract-diff-file",
            str(contract_diff),
            "--max-locked",
            "1",
            "--summary-path",
            str(summary),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    text = summary.read_text(encoding="utf-8")
    assert "queued/running/failed/locked: 0/0/0/1" in text
    assert "locked<=1" in text
