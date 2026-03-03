#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

ARTIFACT_DIR="${ARTIFACT_DIR:-.artifacts}"
PYTHON_BIN="${PYTHON_BIN:-python}"
SUMMARY_PATH="${SUMMARY_PATH:-${GITHUB_STEP_SUMMARY:-}}"

CONTRACT_BASELINE="${CONTRACT_BASELINE:-docs/contract/v2.json}"
CONTRACT_CANDIDATE="${CONTRACT_CANDIDATE:-${ARTIFACT_DIR}/v2_contract_current.json}"
CONTRACT_DIFF="${CONTRACT_DIFF:-${ARTIFACT_DIR}/v2_contract_diff.json}"
CONTRACT_DIFF_VERIFY="${CONTRACT_DIFF_VERIFY:-${ARTIFACT_DIR}/v2_contract_diff_verify.json}"

mkdir -p "${ARTIFACT_DIR}"

step() {
  local name="$1"
  shift
  echo "[v2-ci-suite] ${name}"
  "$@"
}

generate_rc=0
summary_rc=0
verify_rc=0
contract_rc=0
postcheck_rc=0

set +e
step "generate-contract" \
  "${PYTHON_BIN}" scripts/generate-v2-contract.py --output "${CONTRACT_CANDIDATE}"
generate_rc=$?

if [[ -f "${CONTRACT_CANDIDATE}" ]]; then
  step "summarize-contract-diff" \
    "${PYTHON_BIN}" scripts/diff-v2-contract.py \
      --baseline "${CONTRACT_BASELINE}" \
      --candidate "${CONTRACT_CANDIDATE}" \
      --summary-path "${SUMMARY_PATH}" \
      --json-output "${CONTRACT_DIFF}"
  summary_rc=$?

  step "verify-contract-diff" \
    "${PYTHON_BIN}" scripts/diff-v2-contract.py \
      --baseline "${CONTRACT_BASELINE}" \
      --candidate "${CONTRACT_CANDIDATE}" \
      --json-output "${CONTRACT_DIFF_VERIFY}" \
      --fail-on-diff
  verify_rc=$?
else
  echo "[v2-ci-suite] candidate contract missing: ${CONTRACT_CANDIDATE}"
  summary_rc=1
  verify_rc=1
fi

step "runtime-contract-smoke" ./scripts/check-v2-contract.sh
contract_rc=$?

step "postcheck-bundle" ./scripts/run-v2-ci-postchecks.sh
postcheck_rc=$?
set -e

if [[ "${generate_rc}" -ne 0 || "${summary_rc}" -ne 0 || "${verify_rc}" -ne 0 || "${contract_rc}" -ne 0 || "${postcheck_rc}" -ne 0 ]]; then
  exit 1
fi
