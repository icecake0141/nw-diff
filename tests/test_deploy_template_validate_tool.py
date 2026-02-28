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


def test_validate_deploy_templates_json_output_non_strict(tmp_path: Path) -> None:
    json_out = tmp_path / "deploy_validation.json"
    summary_out = tmp_path / "deploy_validation.md"
    result = subprocess.run(
        [
            "bash",
            "scripts/validate-deploy-templates.sh",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            "JSON_OUTPUT": str(json_out),
            "SUMMARY_PATH": str(summary_out),
            "PYTHON_BIN": sys.executable,
        },
    )
    assert result.returncode == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["status"] in {"ok", "failed"}
    assert "warnings_count" in payload
    assert summary_out.exists()


def test_validate_deploy_templates_json_output_strict(tmp_path: Path) -> None:
    json_out = tmp_path / "deploy_validation_strict.json"
    summary_out = tmp_path / "deploy_validation_strict.md"
    result = subprocess.run(
        [
            "bash",
            "scripts/validate-deploy-templates.sh",
            "--strict",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            "JSON_OUTPUT": str(json_out),
            "SUMMARY_PATH": str(summary_out),
            "PYTHON_BIN": sys.executable,
        },
    )
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["strict"] == 1
    assert payload["status"] in {"ok", "failed"}
    if payload["status"] == "failed":
        assert result.returncode == 1
        assert payload["errors_count"] >= 1
    else:
        assert result.returncode == 0
