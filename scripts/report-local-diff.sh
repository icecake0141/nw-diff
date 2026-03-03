#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/report-local-diff.sh
#   ./scripts/report-local-diff.sh --strict --scope v2-migration

# Summarize local worktree changes to keep PR scope small and reviewable.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

STRICT=false
SCOPE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=true
      shift
      ;;
    --scope)
      SCOPE="${2:-}"
      if [[ -z "${SCOPE}" ]]; then
        echo "missing value for --scope"
        exit 2
      fi
      shift 2
      ;;
    *)
      echo "unknown argument: $1"
      exit 2
      ;;
  esac
done

CHANGED_FILES="$(git status --porcelain | awk '{print $2}')"

echo "== Branch =="
git branch --show-current
echo

echo "== Porcelain Status =="
git status --short
echo

echo "== Top-Level Impact =="
printf "%s\n" "${CHANGED_FILES}" | awk -F/ '{print $1}' | sort | uniq -c | sort -nr
echo

echo "== High-Risk Files =="
printf "%s\n" "${CHANGED_FILES}" | rg -n "requirements|\\.github/workflows|Dockerfile|docker-compose|src/nw_diff/app.py" || true
echo

echo "== Suggested Split =="
echo "1) infra/ci: workflow, dependency, deploy scripts"
echo "2) app/api: src/nw_diff*"
echo "3) tests-only: tests/*"
echo "4) docs-only: docs/*"

if [[ "${STRICT}" != "true" ]]; then
  exit 0
fi

echo
echo "== Strict Scope Check =="
if [[ -z "${CHANGED_FILES}" ]]; then
  echo "No local changes."
  exit 0
fi

if [[ -z "${SCOPE}" ]]; then
  echo "Strict mode requires --scope."
  echo "Example: ./scripts/report-local-diff.sh --strict --scope v2-migration"
  exit 2
fi

if [[ "${SCOPE}" != "v2-migration" ]]; then
  echo "Unsupported scope: ${SCOPE}"
  exit 2
fi

ALLOWED_PATTERN='^(src/nw_diff_v2/|tests/test_v2_|scripts/(check-v2-|run-v2-|generate-v2-|diff-v2-|evaluate-v2-|render-v2-|summarize-v2-|report-local-diff\.sh)|docs/(V2_|contract/v2\.json|deploy/)|\.github/workflows/(ci\.yml|integration\.yml)$|docker-compose\.yml$|README\.md$|TODO\.md$|pytest\.ini$)'

DISALLOWED="$(printf "%s\n" "${CHANGED_FILES}" | rg -n -v "${ALLOWED_PATTERN}" || true)"
if [[ -n "${DISALLOWED}" ]]; then
  echo "Out-of-scope files detected for v2 migration:"
  echo "${DISALLOWED}"
  exit 1
fi

echo "Strict v2-migration scope check passed."
