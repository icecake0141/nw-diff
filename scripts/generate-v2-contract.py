#!/usr/bin/env python3
"""
Generate deterministic v2 API contract snapshot JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from nw_diff_v2.api.system import _REQUIRED_ROUTE_CONTRACT  # pylint: disable=wrong-import-position
from nw_diff_v2.main import app  # pylint: disable=wrong-import-position


def _collect_actual_routes() -> list[dict]:
    items: list[dict] = []
    for route in app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/api/v2"):
            continue
        methods = sorted(
            method
            for method in getattr(route, "methods", set())
            if method not in {"HEAD", "OPTIONS"}
        )
        items.append({"path": path, "methods": methods})
    items.sort(key=lambda row: (row["path"], ",".join(row["methods"])))
    return items


def _collect_required_routes() -> list[dict]:
    items = [
        {"path": path, "methods": list(methods)}
        for path, methods in _REQUIRED_ROUTE_CONTRACT
    ]
    items.sort(key=lambda row: (row["path"], ",".join(row["methods"])))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate v2 contract snapshot")
    parser.add_argument(
        "--output",
        default=str(ROOT_DIR / "docs" / "contract" / "v2.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "required_routes": _collect_required_routes(),
        "actual_routes": _collect_actual_routes(),
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
