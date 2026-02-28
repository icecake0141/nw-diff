#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

ARTIFACT_DIR="${ARTIFACT_DIR:-.artifacts}"
SUMMARY_PATH="${SUMMARY_PATH:-${GITHUB_STEP_SUMMARY:-}}"
PYTHON_BIN="${PYTHON_BIN:-python}"

READINESS_FILE="${READINESS_FILE:-${ARTIFACT_DIR}/v2_readiness.json}"
LOCKS_FILE="${LOCKS_FILE:-${ARTIFACT_DIR}/v2_locks.json}"
CONTRACT_DIFF_FILE="${CONTRACT_DIFF_FILE:-${ARTIFACT_DIR}/v2_contract_diff.json}"
DEPLOY_VALIDATION_FILE="${DEPLOY_VALIDATION_FILE:-${ARTIFACT_DIR}/deploy_template_validation.json}"
CUTOVER_EVAL_FILE="${CUTOVER_EVAL_FILE:-${ARTIFACT_DIR}/v2_cutover_eval.json}"
CUTOVER_MD_FILE="${CUTOVER_MD_FILE:-${ARTIFACT_DIR}/v2_cutover_message.md}"
CUTOVER_TXT_FILE="${CUTOVER_TXT_FILE:-${ARTIFACT_DIR}/v2_cutover_message.txt}"

mkdir -p "${ARTIFACT_DIR}"

run_maybe() {
  local name="$1"
  shift
  echo "[v2-postcheck] ${name}"
  "$@"
}

readiness_rc=0
locks_rc=0
evaluate_rc=0
render_md_rc=0
render_txt_rc=0
summary_rc=0

set +e
run_maybe "readiness" \
  "${PYTHON_BIN}" scripts/check-v2-readiness.py \
    --input-file "${READINESS_FILE}" \
    --allow-missing \
    --summary-path "${SUMMARY_PATH}"
readiness_rc=$?

run_maybe "locks" \
  "${PYTHON_BIN}" scripts/check-v2-locks.py \
    --input-file "${LOCKS_FILE}" \
    --max-locks 100 \
    --allow-missing \
    --summary-path "${SUMMARY_PATH}"
locks_rc=$?

run_maybe "evaluate" \
  "${PYTHON_BIN}" scripts/evaluate-v2-cutover.py \
    --readiness-file "${READINESS_FILE}" \
    --contract-diff-file "${CONTRACT_DIFF_FILE}" \
    --deploy-validation-file "${DEPLOY_VALIDATION_FILE}" \
    --allow-missing \
    --summary-path "${SUMMARY_PATH}" \
    --json-output "${CUTOVER_EVAL_FILE}"
evaluate_rc=$?

run_maybe "render-markdown" \
  "${PYTHON_BIN}" scripts/render-v2-cutover-message.py \
    --input "${CUTOVER_EVAL_FILE}" \
    --format markdown \
    --output "${CUTOVER_MD_FILE}" \
    --allow-missing \
    --summary-path "${SUMMARY_PATH}"
render_md_rc=$?

run_maybe "render-text" \
  "${PYTHON_BIN}" scripts/render-v2-cutover-message.py \
    --input "${CUTOVER_EVAL_FILE}" \
    --format text \
    --output "${CUTOVER_TXT_FILE}" \
    --allow-missing
render_txt_rc=$?

run_maybe "summary" ./scripts/summarize-v2-contract.sh
summary_rc=$?
set -e

if [[ "${evaluate_rc}" -ne 0 ]]; then
  exit "${evaluate_rc}"
fi
if [[ "${readiness_rc}" -ne 0 || "${locks_rc}" -ne 0 || "${render_md_rc}" -ne 0 || "${render_txt_rc}" -ne 0 || "${summary_rc}" -ne 0 ]]; then
  exit 1
fi
