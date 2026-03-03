#!/usr/bin/env bash
#
# Copyright 2025 NW-Diff Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
ARTIFACT_DIR="${ARTIFACT_DIR:-.artifacts}"
mkdir -p "$ARTIFACT_DIR"

CONTRACT_CURRENT="${CONTRACT_CURRENT:-${ARTIFACT_DIR}/v2_contract_gate_current.json}"
CONTRACT_DIFF="${CONTRACT_DIFF:-${ARTIFACT_DIR}/v2_contract_gate_diff.json}"

echo "[gate] checking v2 default startup paths"
rg -q "nw_diff_v2.main:app" docker-compose.yml
rg -q "uvicorn nw_diff_v2.main:app" README.md

echo "[gate] checking v2 route contract snapshot"
"${PYTHON_BIN}" scripts/generate-v2-contract.py --output "${CONTRACT_CURRENT}"
"${PYTHON_BIN}" scripts/diff-v2-contract.py \
  --baseline docs/contract/v2.json \
  --candidate "${CONTRACT_CURRENT}" \
  --json-output "${CONTRACT_DIFF}" \
  --fail-on-diff

echo "[gate] checking runtime v2 contract/readiness endpoints"
export DEVICE_PASSWORD="${DEVICE_PASSWORD:-ci_contract_password}"
export NW_DIFF_ENV="${NW_DIFF_ENV:-development}"
export CONTRACT_OUTPUT="${CONTRACT_OUTPUT:-${ARTIFACT_DIR}/v2_contract_gate_runtime.json}"
export HEALTH_OUTPUT="${HEALTH_OUTPUT:-${ARTIFACT_DIR}/v2_health_gate_runtime.json}"
export READINESS_OUTPUT="${READINESS_OUTPUT:-${ARTIFACT_DIR}/v2_readiness_gate_runtime.json}"
export LOCKS_OUTPUT="${LOCKS_OUTPUT:-${ARTIFACT_DIR}/v2_locks_gate_runtime.json}"
export LOG_OUTPUT="${LOG_OUTPUT:-${ARTIFACT_DIR}/v2_contract_gate_runtime.log}"
./scripts/check-v2-contract.sh

echo "[gate] checking required v2 scaffold tests"
"${PYTHON_BIN}" -m pytest -q tests/test_v2_scaffold.py

echo "v2 migration completion gate passed"
