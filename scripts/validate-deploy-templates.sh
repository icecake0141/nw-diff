#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

STRICT=0
if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

SUMMARY_PATH="${SUMMARY_PATH:-${GITHUB_STEP_SUMMARY:-}}"
JSON_OUTPUT="${JSON_OUTPUT:-}"
PYTHON_BIN="${PYTHON_BIN:-python}"
HAS_ERROR=0
WARNINGS=()
ERRORS=()
CHECKS=()

warn_or_fail() {
  local msg="$1"
  if [[ "${STRICT}" -eq 1 ]]; then
    echo "ERROR: ${msg}" >&2
    ERRORS+=("${msg}")
    HAS_ERROR=1
    return 1
  fi
  echo "WARN: ${msg}"
  WARNINGS+=("${msg}")
}

validate_nginx() {
  if ! command -v nginx >/dev/null 2>&1; then
    warn_or_fail "nginx not found; skipping nginx template validation"
    return
  fi

  local tmp_v2_conf
  local tmp_cutover_conf
  tmp_v2_conf="$(mktemp /tmp/nw-diff-nginx-v2-XXXXXX.conf)"
  tmp_cutover_conf="$(mktemp /tmp/nw-diff-nginx-cutover-XXXXXX.conf)"
  cat >"${tmp_v2_conf}" <<EOF
pid /tmp/nginx.pid;
error_log /tmp/nginx-error.log;
events {}
http {
  include ${ROOT_DIR}/docs/deploy/nginx-v2.conf.example;
}
EOF

  cat >"${tmp_cutover_conf}" <<EOF
pid /tmp/nginx.pid;
error_log /tmp/nginx-error.log;
events {}
http {
  include ${ROOT_DIR}/docs/deploy/nginx-v1-v2-cutover.conf.example;
}
EOF

  if ! nginx -t -c "${tmp_v2_conf}"; then
    rm -f "${tmp_v2_conf}" "${tmp_cutover_conf}"
    ERRORS+=("nginx-v2.conf.example failed syntax check")
    HAS_ERROR=1
    return 1
  fi
  if ! nginx -t -c "${tmp_cutover_conf}"; then
    rm -f "${tmp_v2_conf}" "${tmp_cutover_conf}"
    ERRORS+=("nginx-v1-v2-cutover.conf.example failed syntax check")
    HAS_ERROR=1
    return 1
  fi
  rm -f "${tmp_v2_conf}" "${tmp_cutover_conf}"
  CHECKS+=("nginx templates validated")
  echo "OK: nginx templates validated"
}

validate_systemd() {
  if ! command -v systemd-analyze >/dev/null 2>&1; then
    warn_or_fail "systemd-analyze not found; skipping systemd unit validation"
    return
  fi

  local tmp_api_service
  local tmp_worker_service
  tmp_api_service="$(mktemp /tmp/nw-diff-v2-api-XXXXXX.service)"
  tmp_worker_service="$(mktemp /tmp/nw-diff-v2-worker-XXXXXX.service)"
  cp "${ROOT_DIR}/docs/deploy/nw-diff-v2-api.service.example" "${tmp_api_service}"
  cp "${ROOT_DIR}/docs/deploy/nw-diff-v2-worker.service.example" "${tmp_worker_service}"

  if ! systemd-analyze verify \
    "${tmp_api_service}" \
    "${tmp_worker_service}"; then
    rm -f "${tmp_api_service}" "${tmp_worker_service}"
    ERRORS+=("systemd unit templates failed validation")
    HAS_ERROR=1
    return 1
  fi
  rm -f "${tmp_api_service}" "${tmp_worker_service}"
  CHECKS+=("systemd unit templates validated")
  echo "OK: systemd unit templates validated"
}

write_summary() {
  if [[ -z "${SUMMARY_PATH}" ]]; then
    return
  fi
  {
    echo "## Deploy Template Validation"
    echo ""
    if [[ "${HAS_ERROR}" -eq 0 ]]; then
      echo "- status: **ok**"
    else
      echo "- status: **failed**"
    fi
    echo "- strict: ${STRICT}"
    echo "- checks: ${#CHECKS[@]}"
    echo "- warnings: ${#WARNINGS[@]}"
    echo "- errors: ${#ERRORS[@]}"
    if [[ ${#CHECKS[@]} -gt 0 ]]; then
      echo ""
      echo "### Checks"
      for item in "${CHECKS[@]}"; do
        echo "- ${item}"
      done
    fi
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
      echo ""
      echo "### Warnings"
      for item in "${WARNINGS[@]}"; do
        echo "- ${item}"
      done
    fi
    if [[ ${#ERRORS[@]} -gt 0 ]]; then
      echo ""
      echo "### Errors"
      for item in "${ERRORS[@]}"; do
        echo "- ${item}"
      done
    fi
  } >> "${SUMMARY_PATH}"
}

write_json() {
  if [[ -z "${JSON_OUTPUT}" ]]; then
    return
  fi

  local status="ok"
  if [[ "${HAS_ERROR}" -ne 0 ]]; then
    status="failed"
  fi

  CHECKS_LINES="$(printf '%s\n' "${CHECKS[@]:-}")" \
  WARNINGS_LINES="$(printf '%s\n' "${WARNINGS[@]:-}")" \
  ERRORS_LINES="$(printf '%s\n' "${ERRORS[@]:-}")" \
  JSON_OUTPUT_PATH="${JSON_OUTPUT}" \
  STATUS_VALUE="${status}" \
  STRICT_VALUE="${STRICT}" \
  "${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

def _to_list(env_key: str) -> list[str]:
    raw = os.environ.get(env_key, "")
    if not raw:
        return []
    return [line for line in raw.splitlines() if line]

payload = {
    "status": os.environ.get("STATUS_VALUE", "ok"),
    "strict": int(os.environ.get("STRICT_VALUE", "0")),
    "checks": _to_list("CHECKS_LINES"),
    "warnings": _to_list("WARNINGS_LINES"),
    "errors": _to_list("ERRORS_LINES"),
}
payload["checks_count"] = len(payload["checks"])
payload["warnings_count"] = len(payload["warnings"])
payload["errors_count"] = len(payload["errors"])

out = Path(os.environ["JSON_OUTPUT_PATH"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

validate_nginx || true
validate_systemd || true
write_summary
write_json

if [[ "${HAS_ERROR}" -ne 0 ]]; then
  exit 1
fi
echo "deploy template validation completed"
