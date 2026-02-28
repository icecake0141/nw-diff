#!/usr/bin/env python3
"""Check v2 readiness payload and exit non-zero on degraded state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen


def _load_payload(*, input_file: str, url: str) -> dict:
    if input_file:
        return json.loads(Path(input_file).read_text(encoding="utf-8"))
    with urlopen(url, timeout=10) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check NW-Diff v2 readiness")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:18080/api/v2/system/readiness",
        help="Readiness endpoint URL",
    )
    parser.add_argument(
        "--input-file",
        default="",
        help="Read readiness payload from JSON file instead of URL",
    )
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="Exit 0 even when status is degraded",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional markdown output path",
    )
    args = parser.parse_args()

    payload = _load_payload(input_file=args.input_file, url=args.url)
    status = str(payload.get("status", "unknown"))
    checks = payload.get("checks", [])
    counts = payload.get("counts", {})

    print(f"readiness status={status}")
    print(f"checks={len(checks)} counts={counts}")

    if args.summary_path:
        out = Path(args.summary_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "## V2 Readiness",
            "",
            f"- status: **{status}**",
            f"- checks: {len(checks)}",
            f"- counts: `{json.dumps(counts, ensure_ascii=False, sort_keys=True)}`",
        ]
        with out.open("a", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")

    if status == "ok":
        return 0
    if status == "degraded" and args.allow_degraded:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
