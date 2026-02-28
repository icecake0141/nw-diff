"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring

from pathlib import Path
import subprocess
import sys


def test_summarize_v2_contract_handles_missing_contract_file(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        ["bash", "scripts/summarize-v2-contract.sh"],
        check=False,
        capture_output=True,
        text=True,
        env={
            "GITHUB_STEP_SUMMARY": str(summary),
            "CONTRACT_OUTPUT": str(tmp_path / "missing.json"),
            "PYTHON_BIN": sys.executable,
        },
    )
    assert result.returncode == 0
    text = summary.read_text(encoding="utf-8")
    assert "status: unavailable" in text
    assert "contract output file not found" in text


def test_summarize_v2_contract_handles_malformed_json(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    contract = tmp_path / "contract.json"
    contract.write_text("", encoding="utf-8")
    result = subprocess.run(
        ["bash", "scripts/summarize-v2-contract.sh"],
        check=False,
        capture_output=True,
        text=True,
        env={
            "GITHUB_STEP_SUMMARY": str(summary),
            "CONTRACT_OUTPUT": str(contract),
            "PYTHON_BIN": sys.executable,
        },
    )
    assert result.returncode == 0
    text = summary.read_text(encoding="utf-8")
    assert "status: **unavailable**" in text
    assert "contract_file_error" in text
