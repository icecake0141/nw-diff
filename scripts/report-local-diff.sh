#!/usr/bin/env bash
set -euo pipefail

# Summarize local worktree changes to keep PR scope small and reviewable.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

echo "== Branch =="
git branch --show-current
echo

echo "== Porcelain Status =="
git status --short
echo

echo "== Top-Level Impact =="
git status --porcelain | awk '{print $2}' | awk -F/ '{print $1}' | sort | uniq -c | sort -nr
echo

echo "== High-Risk Files =="
git status --porcelain | awk '{print $2}' | rg -n "requirements|\\.github/workflows|Dockerfile|docker-compose|src/nw_diff/app.py" || true
echo

echo "== Suggested Split =="
echo "1) infra/ci: workflow, dependency, deploy scripts"
echo "2) app/api: src/nw_diff*"
echo "3) tests-only: tests/*"
echo "4) docs-only: docs/*"
