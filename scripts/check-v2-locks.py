#!/usr/bin/env python3
"""Check v2 lock payload and exit non-zero when limits are exceeded."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen


def _load_payload(*, input_file: str, url: str) -> dict | None:
    if input_file:
        path = Path(input_file)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    with urlopen(url, timeout=10) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check NW-Diff v2 lock status")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:18080/api/v2/system/locks",
        help="Lock endpoint URL",
    )
    parser.add_argument(
        "--input-file",
        default="",
        help="Read lock payload from JSON file instead of URL",
    )
    parser.add_argument(
        "--max-locks",
        type=int,
        default=100,
        help="Maximum allowed active lock rows",
    )
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Exit 0 even when stale lock rows are present",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Exit 0 when input file/url payload is unavailable",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional markdown output path",
    )
    args = parser.parse_args()

    payload = _load_payload(input_file=args.input_file, url=args.url)
    if payload is None:
        print("lock payload unavailable")
        if args.summary_path:
            out = Path(args.summary_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "## V2 Locks",
                "",
                "- status: **missing_input**",
                f"- input_file: `{args.input_file}`",
            ]
            with out.open("a", encoding="utf-8") as fp:
                fp.write("\n".join(lines) + "\n")
        return 0 if args.allow_missing else 1
    locks = payload.get("locks", [])
    count = int(payload.get("count", len(locks)))
    stale_count = sum(1 for row in locks if bool(row.get("is_stale", False)))

    print(f"locks count={count} stale={stale_count} max_locks={args.max_locks}")

    reasons: list[str] = []
    if count > int(args.max_locks):
        reasons.append(f"count={count} exceeds max_locks={int(args.max_locks)}")
    if stale_count > 0 and not args.allow_stale:
        reasons.append(f"stale locks detected: {stale_count}")

    if args.summary_path:
        out = Path(args.summary_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "## V2 Locks",
            "",
            f"- count: {count}",
            f"- stale: {stale_count}",
            f"- max_locks: {int(args.max_locks)}",
            f"- allow_stale: {bool(args.allow_stale)}",
            f"- status: **{'ok' if not reasons else 'failed'}**",
        ]
        if reasons:
            lines.extend(["", "### Reasons", *[f"- {reason}" for reason in reasons]])
        with out.open("a", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")

    if reasons:
        for reason in reasons:
            print(f"ERROR: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
