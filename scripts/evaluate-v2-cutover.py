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

Evaluate v2 cutover Go/No-Go from readiness and contract diff outputs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _load_json(path: str) -> dict | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate v2 cutover readiness")
    parser.add_argument("--readiness-file", required=True, help="Readiness JSON path")
    parser.add_argument(
        "--contract-diff-file", required=True, help="Contract diff JSON path"
    )
    parser.add_argument(
        "--deploy-validation-file",
        default="",
        help="Optional deploy template validation JSON path",
    )
    parser.add_argument("--max-queued", type=int, default=None)
    parser.add_argument("--max-running", type=int, default=None)
    parser.add_argument("--max-failed", type=int, default=None)
    parser.add_argument("--max-locked", type=int, default=None)
    parser.add_argument("--summary-path", default="")
    parser.add_argument("--json-output", default="")
    parser.add_argument("--allow-no-go", action="store_true")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Exit 0 when required input JSON files are unavailable",
    )
    args = parser.parse_args()

    max_queued = (
        int(args.max_queued)
        if args.max_queued is not None
        else _env_int("V2_CUTOVER_MAX_QUEUED", 0)
    )
    max_running = (
        int(args.max_running)
        if args.max_running is not None
        else _env_int("V2_CUTOVER_MAX_RUNNING", 5)
    )
    max_failed = (
        int(args.max_failed)
        if args.max_failed is not None
        else _env_int("V2_CUTOVER_MAX_FAILED", 0)
    )
    max_locked = (
        int(args.max_locked)
        if args.max_locked is not None
        else _env_int("V2_CUTOVER_MAX_LOCKED", 0)
    )

    readiness = _load_json(args.readiness_file)
    contract_diff = _load_json(args.contract_diff_file)
    if readiness is None or contract_diff is None:
        missing_files: list[str] = []
        if readiness is None:
            missing_files.append(args.readiness_file)
        if contract_diff is None:
            missing_files.append(args.contract_diff_file)
        payload = {
            "go": False,
            "readiness_status": "missing_input",
            "has_contract_diff": False,
            "deploy_validation_status": "skipped",
            "counts": {"queued": 0, "running": 0, "failed": 0, "locked_hosts": 0},
            "limits": {
                "max_queued": max_queued,
                "max_running": max_running,
                "max_failed": max_failed,
                "max_locked": max_locked,
            },
            "reasons": [f"missing input file: {path}" for path in missing_files],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if args.summary_path:
            out = Path(args.summary_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("a", encoding="utf-8") as fp:
                fp.write(
                    "## V2 Cutover Evaluation\n\n- decision: **NO-GO**\n"
                    "- readiness_status: missing_input\n"
                    "### Reasons\n"
                    + "\n".join(
                        [f"- missing input file: {path}" for path in missing_files]
                    )
                    + "\n"
                )
        if args.json_output:
            out = Path(args.json_output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        return 0 if args.allow_missing else 1
    deploy_validation = (
        _load_json(args.deploy_validation_file) if args.deploy_validation_file else {}
    )

    reasons: list[str] = []
    readiness_status = str(readiness.get("status", "unknown"))
    counts = readiness.get("counts", {})
    queued = int(counts.get("queued", 0))
    running = int(counts.get("running", 0))
    failed = int(counts.get("failed", 0))
    locked = int(counts.get("locked_hosts", counts.get("locked", 0)))
    has_contract_diff = bool(contract_diff.get("has_diff", False))
    deploy_status = (
        str(deploy_validation.get("status", "unknown"))
        if deploy_validation
        else "skipped"
    )

    if readiness_status != "ok":
        reasons.append(f"readiness status is {readiness_status}")
    if has_contract_diff:
        reasons.append("contract diff has changes")
    if deploy_validation and deploy_status != "ok":
        reasons.append(f"deploy template validation status is {deploy_status}")
    if queued > max_queued:
        reasons.append(f"queued={queued} exceeds max_queued={max_queued}")
    if running > max_running:
        reasons.append(f"running={running} exceeds max_running={max_running}")
    if failed > max_failed:
        reasons.append(f"failed={failed} exceeds max_failed={max_failed}")
    if locked > max_locked:
        reasons.append(f"locked_hosts={locked} exceeds max_locked={max_locked}")

    go = len(reasons) == 0
    payload = {
        "go": go,
        "readiness_status": readiness_status,
        "has_contract_diff": has_contract_diff,
        "deploy_validation_status": deploy_status,
        "counts": {
            "queued": queued,
            "running": running,
            "failed": failed,
            "locked_hosts": locked,
        },
        "limits": {
            "max_queued": max_queued,
            "max_running": max_running,
            "max_failed": max_failed,
            "max_locked": max_locked,
        },
        "reasons": reasons,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if args.summary_path:
        out = Path(args.summary_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "## V2 Cutover Evaluation",
            "",
            f"- decision: **{'GO' if go else 'NO-GO'}**",
            f"- readiness_status: {readiness_status}",
            f"- has_contract_diff: {has_contract_diff}",
            f"- deploy_validation_status: {deploy_status}",
            f"- queued/running/failed/locked: {queued}/{running}/{failed}/{locked}",
            f"- limits: queued<={max_queued}, running<={max_running}, failed<={max_failed}, locked<={max_locked}",
        ]
        if reasons:
            lines.extend(["", "### Reasons"])
            lines.extend([f"- {reason}" for reason in reasons])
        with out.open("a", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")

    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if go or args.allow_no_go:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
