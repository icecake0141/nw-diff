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

Generate deterministic v2 API contract snapshot JSON.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))


def _collect_actual_routes() -> list[dict]:
    app = importlib.import_module("nw_diff_v2.main").app
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
    required_route_contract = importlib.import_module(
        "nw_diff_v2.api.system"
    )._REQUIRED_ROUTE_CONTRACT
    items = [
        {"path": path, "methods": list(methods)}
        for path, methods in required_route_contract
    ]
    items.sort(key=lambda row: (row["path"], ",".join(row["methods"])))
    return items


def main() -> int:
    """Generate and write the deterministic v2 contract snapshot JSON."""
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
