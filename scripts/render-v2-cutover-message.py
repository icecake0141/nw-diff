#!/usr/bin/env python3
"""Render a human-readable cutover status message from evaluation JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _render_markdown(payload: dict) -> str:
    go = bool(payload.get("go", False))
    decision = "GO" if go else "NO-GO"
    readiness_status = str(payload.get("readiness_status", "unknown"))
    deploy_status = str(payload.get("deploy_validation_status", "unknown"))
    has_contract_diff = bool(payload.get("has_contract_diff", False))
    counts = payload.get("counts", {})
    limits = payload.get("limits", {})
    reasons = payload.get("reasons", [])

    lines = [
        "## V2 Cutover Notification",
        "",
        f"- decision: **{decision}**",
        f"- readiness_status: {readiness_status}",
        f"- deploy_validation_status: {deploy_status}",
        f"- has_contract_diff: {has_contract_diff}",
        f"- counts: queued={counts.get('queued', 0)}, running={counts.get('running', 0)}, failed={counts.get('failed', 0)}, locked={counts.get('locked_hosts', 0)}",
        f"- limits: queued<={limits.get('max_queued', '-')}, running<={limits.get('max_running', '-')}, failed<={limits.get('max_failed', '-')}, locked<={limits.get('max_locked', '-')}",
    ]
    if reasons:
        lines.extend(["", "### Reasons", *[f"- {reason}" for reason in reasons]])
    else:
        lines.extend(["", "- No blocking reasons."])
    return "\n".join(lines) + "\n"


def _render_text(payload: dict) -> str:
    go = bool(payload.get("go", False))
    decision = "GO" if go else "NO-GO"
    reasons = payload.get("reasons", [])
    base = f"[NW-Diff v2] Cutover decision: {decision}"
    if reasons:
        return base + " | reasons: " + "; ".join(str(r) for r in reasons)
    return base + " | reasons: none"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render cutover message")
    parser.add_argument("--input", required=True, help="Path to v2_cutover_eval.json")
    parser.add_argument(
        "--format",
        choices=("markdown", "text"),
        default="markdown",
        help="Message output format",
    )
    parser.add_argument("--output", default="", help="Optional output file path")
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional path to append markdown summary",
    )
    args = parser.parse_args()

    payload = _load(args.input)
    message = _render_markdown(payload) if args.format == "markdown" else _render_text(payload)
    print(message)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(message, encoding="utf-8")

    if args.summary_path and args.format == "markdown":
        summary = Path(args.summary_path)
        summary.parent.mkdir(parents=True, exist_ok=True)
        with summary.open("a", encoding="utf-8") as fp:
            fp.write(message)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
