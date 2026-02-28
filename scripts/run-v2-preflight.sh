#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
ARTIFACT_DIR="${ARTIFACT_DIR:-.artifacts}"
ALLOW_NO_GO="${ALLOW_NO_GO:-false}"

mkdir -p "${ARTIFACT_DIR}"

CONTRACT_OUTPUT="${CONTRACT_OUTPUT:-${ARTIFACT_DIR}/v2_contract.json}"
HEALTH_OUTPUT="${HEALTH_OUTPUT:-${ARTIFACT_DIR}/v2_health.json}"
READINESS_OUTPUT="${READINESS_OUTPUT:-${ARTIFACT_DIR}/v2_readiness.json}"
LOCKS_OUTPUT="${LOCKS_OUTPUT:-${ARTIFACT_DIR}/v2_locks.json}"
LOG_OUTPUT="${LOG_OUTPUT:-${ARTIFACT_DIR}/v2_contract.log}"
CONTRACT_DIFF_OUTPUT="${CONTRACT_DIFF_OUTPUT:-${ARTIFACT_DIR}/v2_contract_diff.json}"
CONTRACT_CURRENT_OUTPUT="${CONTRACT_CURRENT_OUTPUT:-${ARTIFACT_DIR}/v2_contract_current.json}"
CUTOVER_EVAL_OUTPUT="${CUTOVER_EVAL_OUTPUT:-${ARTIFACT_DIR}/v2_cutover_eval.json}"
CUTOVER_MSG_MD="${CUTOVER_MSG_MD:-${ARTIFACT_DIR}/v2_cutover_message.md}"
CUTOVER_MSG_TXT="${CUTOVER_MSG_TXT:-${ARTIFACT_DIR}/v2_cutover_message.txt}"
DEPLOY_VALIDATION_FILE="${DEPLOY_VALIDATION_FILE:-${ARTIFACT_DIR}/deploy_template_validation.json}"
DEPLOY_VALIDATION_STRICT="${DEPLOY_VALIDATION_STRICT:-false}"
SUMMARY_PATH="${SUMMARY_PATH:-}"

echo "[1/7] Running v2 contract smoke check..."
PYTHON_BIN="${PYTHON_BIN}" \
CONTRACT_OUTPUT="${CONTRACT_OUTPUT}" \
HEALTH_OUTPUT="${HEALTH_OUTPUT}" \
READINESS_OUTPUT="${READINESS_OUTPUT}" \
LOCKS_OUTPUT="${LOCKS_OUTPUT}" \
LOG_OUTPUT="${LOG_OUTPUT}" \
./scripts/check-v2-contract.sh

echo "[2/7] Generating contract diff artifact..."
"${PYTHON_BIN}" scripts/generate-v2-contract.py \
  --output "${CONTRACT_CURRENT_OUTPUT}"
"${PYTHON_BIN}" scripts/diff-v2-contract.py \
  --baseline docs/contract/v2.json \
  --candidate "${CONTRACT_CURRENT_OUTPUT}" \
  --json-output "${CONTRACT_DIFF_OUTPUT}"

echo "[3/7] Running readiness check..."
READINESS_ARGS=(
  scripts/check-v2-readiness.py
  --input-file "${READINESS_OUTPUT}"
)
if [[ -n "${SUMMARY_PATH}" ]]; then
  READINESS_ARGS+=(--summary-path "${SUMMARY_PATH}")
fi
"${PYTHON_BIN}" "${READINESS_ARGS[@]}"

echo "[4/7] Running locks check..."
LOCKS_ARGS=(
  scripts/check-v2-locks.py
  --input-file "${LOCKS_OUTPUT}"
  --max-locks "${V2_CONTRACT_MAX_LOCKS:-100}"
)
if [[ "${V2_CONTRACT_ALLOW_STALE_LOCKS:-false}" == "true" ]]; then
  LOCKS_ARGS+=(--allow-stale)
fi
if [[ -n "${SUMMARY_PATH}" ]]; then
  LOCKS_ARGS+=(--summary-path "${SUMMARY_PATH}")
fi
"${PYTHON_BIN}" "${LOCKS_ARGS[@]}"

echo "[5/7] Validating deploy templates..."
DEPLOY_VALIDATE_ARGS=(
  ./scripts/validate-deploy-templates.sh
)
if [[ "${DEPLOY_VALIDATION_STRICT}" == "true" ]]; then
  DEPLOY_VALIDATE_ARGS+=(--strict)
fi
SUMMARY_PATH="${SUMMARY_PATH}" \
JSON_OUTPUT="${DEPLOY_VALIDATION_FILE}" \
PYTHON_BIN="${PYTHON_BIN}" \
bash "${DEPLOY_VALIDATE_ARGS[@]}"

echo "[6/7] Evaluating cutover go/no-go..."
CUTOVER_ARGS=(
  scripts/evaluate-v2-cutover.py
  --readiness-file "${READINESS_OUTPUT}"
  --contract-diff-file "${CONTRACT_DIFF_OUTPUT}"
  --deploy-validation-file "${DEPLOY_VALIDATION_FILE}"
  --json-output "${CUTOVER_EVAL_OUTPUT}"
)
if [[ -n "${SUMMARY_PATH}" ]]; then
  CUTOVER_ARGS+=(--summary-path "${SUMMARY_PATH}")
fi
if [[ "${ALLOW_NO_GO}" == "true" ]]; then
  CUTOVER_ARGS+=(--allow-no-go)
fi
"${PYTHON_BIN}" "${CUTOVER_ARGS[@]}"

echo "[7/7] Rendering cutover messages..."
MSG_MD_ARGS=(
  scripts/render-v2-cutover-message.py
  --input "${CUTOVER_EVAL_OUTPUT}"
  --format markdown
  --output "${CUTOVER_MSG_MD}"
)
if [[ -n "${SUMMARY_PATH}" ]]; then
  MSG_MD_ARGS+=(--summary-path "${SUMMARY_PATH}")
fi
"${PYTHON_BIN}" "${MSG_MD_ARGS[@]}"
"${PYTHON_BIN}" scripts/render-v2-cutover-message.py \
  --input "${CUTOVER_EVAL_OUTPUT}" \
  --format text \
  --output "${CUTOVER_MSG_TXT}"

echo "Preflight completed."
echo "Artifacts:"
echo "  - ${CONTRACT_OUTPUT}"
echo "  - ${HEALTH_OUTPUT}"
echo "  - ${READINESS_OUTPUT}"
echo "  - ${LOCKS_OUTPUT}"
echo "  - ${CONTRACT_DIFF_OUTPUT}"
echo "  - ${CONTRACT_CURRENT_OUTPUT}"
echo "  - ${DEPLOY_VALIDATION_FILE}"
echo "  - ${CUTOVER_EVAL_OUTPUT}"
echo "  - ${CUTOVER_MSG_MD}"
echo "  - ${CUTOVER_MSG_TXT}"
