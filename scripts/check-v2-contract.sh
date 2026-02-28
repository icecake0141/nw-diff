#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

HOST="127.0.0.1"
PORT="${V2_CONTRACT_PORT:-18080}"
BASE_URL="http://${HOST}:${PORT}"
export PYTHON_BIN="${PYTHON_BIN:-python}"
export CONTRACT_OUTPUT="${CONTRACT_OUTPUT:-/tmp/v2_contract.json}"
export HEALTH_OUTPUT="${HEALTH_OUTPUT:-/tmp/v2_health.json}"
export READINESS_OUTPUT="${READINESS_OUTPUT:-/tmp/v2_readiness.json}"
export LOCKS_OUTPUT="${LOCKS_OUTPUT:-/tmp/v2_locks.json}"
export LOG_OUTPUT="${LOG_OUTPUT:-/tmp/nw_diff_v2_contract.log}"
export V2_CONTRACT_MAX_LOCKS="${V2_CONTRACT_MAX_LOCKS:-100}"
export V2_CONTRACT_ALLOW_STALE_LOCKS="${V2_CONTRACT_ALLOW_STALE_LOCKS:-false}"

export DEVICE_PASSWORD="${DEVICE_PASSWORD:-contract_check_password}"
export NW_DIFF_ENV="${NW_DIFF_ENV:-development}"

CURL_AUTH_ARGS=()
if [[ -n "${NW_DIFF_API_TOKEN:-}" ]]; then
  CURL_AUTH_ARGS+=(-H "Authorization: Bearer ${NW_DIFF_API_TOKEN}")
elif [[ -n "${NW_DIFF_BASIC_USER:-}" && -n "${NW_DIFF_BASIC_PASSWORD:-}" ]]; then
  CURL_AUTH_ARGS+=(-u "${NW_DIFF_BASIC_USER}:${NW_DIFF_BASIC_PASSWORD}")
fi

cleanup() {
  if [[ -n "${APP_PID:-}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    kill "${APP_PID}" || true
    wait "${APP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

"${PYTHON_BIN}" -m uvicorn nw_diff_v2.main:app --host "${HOST}" --port "${PORT}" --app-dir src >"${LOG_OUTPUT}" 2>&1 &
APP_PID=$!

for _ in $(seq 1 40); do
  if curl -fsS "${CURL_AUTH_ARGS[@]}" "${BASE_URL}/api/v2/system/health" >"${HEALTH_OUTPUT}" 2>/dev/null; then
    break
  fi
  sleep 0.25
done

if ! curl -fsS "${CURL_AUTH_ARGS[@]}" "${BASE_URL}/api/v2/system/contract" >"${CONTRACT_OUTPUT}"; then
  echo "Failed to fetch contract endpoint"
  cat "${LOG_OUTPUT}" || true
  exit 1
fi
if ! curl -fsS "${CURL_AUTH_ARGS[@]}" "${BASE_URL}/api/v2/system/readiness" >"${READINESS_OUTPUT}"; then
  echo "Failed to fetch readiness endpoint"
  cat "${LOG_OUTPUT}" || true
  exit 1
fi
if ! curl -fsS "${CURL_AUTH_ARGS[@]}" "${BASE_URL}/api/v2/system/locks" >"${LOCKS_OUTPUT}"; then
  echo "Failed to fetch locks endpoint"
  cat "${LOG_OUTPUT}" || true
  exit 1
fi

LOCK_CHECK_ARGS=(
  scripts/check-v2-locks.py
  --input-file "${LOCKS_OUTPUT}"
  --max-locks "${V2_CONTRACT_MAX_LOCKS}"
)
if [[ "${V2_CONTRACT_ALLOW_STALE_LOCKS}" == "true" ]]; then
  LOCK_CHECK_ARGS+=(--allow-stale)
fi
"${PYTHON_BIN}" "${LOCK_CHECK_ARGS[@]}"

"${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(
    Path(os.environ.get("CONTRACT_OUTPUT", "/tmp/v2_contract.json")).read_text(
        encoding="utf-8"
    )
)
readiness = json.loads(
    Path(os.environ.get("READINESS_OUTPUT", "/tmp/v2_readiness.json")).read_text(
        encoding="utf-8"
    )
)
status = payload.get("status")
missing = payload.get("missing", [])
readiness_status = readiness.get("status")

if status != "ok" or missing or readiness_status != "ok":
    raise SystemExit(
        "Contract/readiness check failed: "
        f"contract_status={status}, missing={missing}, readiness_status={readiness_status}"
    )
print("v2 contract check passed")
PY
