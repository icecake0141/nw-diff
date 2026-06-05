#!/usr/bin/env python3
"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.

Compare v2 contract snapshots and emit a readable summary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _route_set(payload: dict, key: str) -> set[tuple[str, tuple[str, ...]]]:
    rows = payload.get(key, [])
    result: set[tuple[str, tuple[str, ...]]] = set()
    for row in rows:
        path = str(row.get("path", ""))
        methods = tuple(sorted(str(m) for m in row.get("methods", [])))
        result.add((path, methods))
    return result


def _to_markdown_lines(
    baseline_path: Path,
    candidate_path: Path,
    *,
    required_added: list[tuple[str, tuple[str, ...]]],
    required_removed: list[tuple[str, tuple[str, ...]]],
    actual_added: list[tuple[str, tuple[str, ...]]],
    actual_removed: list[tuple[str, tuple[str, ...]]],
) -> list[str]:
    lines = [
        "## V2 Contract Snapshot Diff",
        "",
        f"- baseline: `{baseline_path}`",
        f"- candidate: `{candidate_path}`",
        f"- required added: {len(required_added)}",
        f"- required removed: {len(required_removed)}",
        f"- actual added: {len(actual_added)}",
        f"- actual removed: {len(actual_removed)}",
    ]

    def _append_section(title: str, rows: list[tuple[str, tuple[str, ...]]]) -> None:
        if not rows:
            return
        lines.append("")
        lines.append(f"### {title}")
        for path, methods in rows:
            lines.append(f"- `{path}` {list(methods)}")

    _append_section("Required Added", required_added)
    _append_section("Required Removed", required_removed)
    _append_section("Actual Added", actual_added)
    _append_section("Actual Removed", actual_removed)

    if (
        not required_added
        and not required_removed
        and not actual_added
        and not actual_removed
    ):
        lines.extend(["", "- No differences detected."])
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff v2 contract snapshots")
    parser.add_argument("--baseline", required=True, help="Baseline JSON path")
    parser.add_argument("--candidate", required=True, help="Candidate JSON path")
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional markdown output path (appends if exists)",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional JSON output path",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit 1 when differences are detected",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)

    base_required = _route_set(baseline, "required_routes")
    cand_required = _route_set(candidate, "required_routes")
    base_actual = _route_set(baseline, "actual_routes")
    cand_actual = _route_set(candidate, "actual_routes")

    required_added = sorted(cand_required.difference(base_required))
    required_removed = sorted(base_required.difference(cand_required))
    actual_added = sorted(cand_actual.difference(base_actual))
    actual_removed = sorted(base_actual.difference(cand_actual))

    lines = _to_markdown_lines(
        baseline_path,
        candidate_path,
        required_added=required_added,
        required_removed=required_removed,
        actual_added=actual_added,
        actual_removed=actual_removed,
    )
    text = "\n".join(lines) + "\n"
    print(text, end="")

    payload = {
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "required_added": [
            {"path": path, "methods": list(methods)} for path, methods in required_added
        ],
        "required_removed": [
            {"path": path, "methods": list(methods)}
            for path, methods in required_removed
        ],
        "actual_added": [
            {"path": path, "methods": list(methods)} for path, methods in actual_added
        ],
        "actual_removed": [
            {"path": path, "methods": list(methods)} for path, methods in actual_removed
        ],
        "has_diff": bool(
            required_added or required_removed or actual_added or actual_removed
        ),
    }

    if args.summary_path:
        summary_path = Path(args.summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("a", encoding="utf-8") as fp:
            fp.write(text)

    if args.json_output:
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    has_diff = bool(payload["has_diff"])
    if args.fail_on_diff and has_diff:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
