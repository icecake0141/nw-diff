"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nw_diff.diff import compute_diff  # noqa: E402


def test_inline_context_only_includes_adjacent_lines() -> None:
    origin = "\n".join(["keep-1", "change-me", "keep-2", "omit-1", "omit-2"])
    dest = "\n".join(["keep-1", "change-me-updated", "keep-2", "omit-1", "omit-2"])

    status, html = compute_diff(
        origin, dest, view="inline", diff_mode="context", context_lines=1
    )

    assert status == "changes detected"
    assert "keep-1" in html
    assert "keep-2" in html
    assert "omit-1" not in html
    assert "omit-2" not in html
    assert "..." in html
    assert "<del" in html or "<ins" in html


def test_side_by_side_context_collapses_unrelated_lines() -> None:
    origin = "\n".join(["head-1", "delta", "head-2", "tail-1", "tail-2"])
    dest = "\n".join(["head-1", "delta-updated", "head-2", "tail-1", "tail-2"])

    status, html = compute_diff(
        origin, dest, view="sidebyside", diff_mode="context", context_lines=1
    )

    assert status == "changes detected"
    assert "head-1" in html
    assert "head-2" in html
    assert "tail-1" not in html
    assert "tail-2" not in html
    assert "..." in html
