#!/usr/bin/env bash
set -euo pipefail

CONTRACT_OUTPUT="${CONTRACT_OUTPUT:-.artifacts/v2_contract.json}"
HEALTH_OUTPUT="${HEALTH_OUTPUT:-.artifacts/v2_health.json}"
READINESS_OUTPUT="${READINESS_OUTPUT:-.artifacts/v2_readiness.json}"
LOCKS_OUTPUT="${LOCKS_OUTPUT:-.artifacts/v2_locks.json}"
LOG_OUTPUT="${LOG_OUTPUT:-.artifacts/v2_contract.log}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -z "${GITHUB_STEP_SUMMARY:-}" ]]; then
  # No-op outside GitHub Actions summary context.
  exit 0
fi

if [[ ! -f "${CONTRACT_OUTPUT}" ]]; then
  {
    echo "## V2 Contract Check"
    echo ""
    echo "- status: unavailable"
    echo "- reason: contract output file not found (\`${CONTRACT_OUTPUT}\`)"
  } >>"${GITHUB_STEP_SUMMARY}"
  exit 0
fi

"${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

contract_path = Path(os.environ.get("CONTRACT_OUTPUT", ".artifacts/v2_contract.json"))
health_path = Path(os.environ.get("HEALTH_OUTPUT", ".artifacts/v2_health.json"))
readiness_path = Path(os.environ.get("READINESS_OUTPUT", ".artifacts/v2_readiness.json"))
locks_path = Path(os.environ.get("LOCKS_OUTPUT", ".artifacts/v2_locks.json"))
log_path = Path(os.environ.get("LOG_OUTPUT", ".artifacts/v2_contract.log"))
summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])

contract = json.loads(contract_path.read_text(encoding="utf-8"))
health = {}
if health_path.exists():
    try:
        health = json.loads(health_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        health = {}
readiness = {}
if readiness_path.exists():
    try:
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        readiness = {}
locks = {}
if locks_path.exists():
    try:
        locks = json.loads(locks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        locks = {}

status = str(contract.get("status", "unknown"))
required_count = int(contract.get("required_count", 0))
actual_count = int(contract.get("actual_count", 0))
missing = contract.get("missing", [])
extra = contract.get("extra", [])

lines = [
    "## V2 Contract Check",
    "",
    f"- status: **{status}**",
    f"- required_count: {required_count}",
    f"- actual_count: {actual_count}",
    f"- missing: {len(missing)}",
    f"- extra: {len(extra)}",
]

if health:
    lines.extend(
        [
            "",
            "### Health",
            f"- status: {health.get('status', 'unknown')}",
            f"- db_url: `{health.get('db_url', '')}`",
            f"- artifact_root: `{health.get('artifact_root', '')}`",
        ]
    )

if readiness:
    lines.extend(
        [
            "",
            "### Readiness",
            f"- status: {readiness.get('status', 'unknown')}",
            f"- checks: {len(readiness.get('checks', []))}",
            f"- queued: {readiness.get('counts', {}).get('queued', 0)}",
            f"- running: {readiness.get('counts', {}).get('running', 0)}",
            f"- failed: {readiness.get('counts', {}).get('failed', 0)}",
            f"- locked_hosts: {readiness.get('counts', {}).get('locked_hosts', 0)}",
        ]
    )

if locks:
    stale_count = sum(1 for row in locks.get("locks", []) if bool(row.get("is_stale", False)))
    lines.extend(
        [
            "",
            "### Locks",
            f"- count: {locks.get('count', 0)}",
            f"- stale: {stale_count}",
            f"- timeout_seconds: {locks.get('timeout_seconds', 0)}",
        ]
    )

if missing:
    lines.append("")
    lines.append("### Missing Routes")
    for item in missing:
        lines.append(f"- `{item.get('path', '')}` {item.get('methods', [])}")

if extra:
    lines.append("")
    lines.append("### Extra Routes")
    for item in extra:
        lines.append(f"- `{item.get('path', '')}` {item.get('methods', [])}")

if log_path.exists():
    raw = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = raw[-20:]
    if tail:
        lines.extend(["", "### Contract Check Log (tail)", "```text", *tail, "```"])

with summary_path.open("a", encoding="utf-8") as fp:
    fp.write("\n".join(lines) + "\n")
PY
