# V2 Commit Split Plan

This document records the completed split and proposes next PR slices after v2 stabilization.

## Current State

- Initial v2 scaffold split (`v2-core`, `v2-ops`, `v2-deploy`, `ci(v2)`, `docs(v2)`) is already merged.
- Current follow-up branch: `codex/reimpl-scaffold` (post-merge hardening work).

## Preconditions

- Exclude generated files from commits:
  - `.artifacts/*`
  - `nw_diff_v2.db`
- Verify tests before each commit:
  - `.venv/bin/pytest -q tests`

## Recommended Next PR Slices

1. `fix(ci-v2): auth and artifact hardening`
   - `scripts/check-v2-contract.sh`
   - `scripts/summarize-v2-contract.sh`
   - `requirements-dev.txt` (`httpx` for FastAPI TestClient)
   - `tests/test_v2_contract_summary_tool.py`

2. `fix(deploy-validation): syntax-only host-agnostic checks`
   - `scripts/validate-deploy-templates.sh`

3. `ci(v2): consolidate duplicated post-check steps`
   - `.github/workflows/ci.yml`
   - `.github/workflows/integration.yml`
   - `scripts/run-v2-ci-postchecks.sh`

4. `docs(v2-ops): runbook and status refresh`
   - `docs/V2_RUNBOOK.md`
   - `docs/V2_IMPLEMENTATION_STATUS.md`
   - `CHANGELOG.md`
   - `.gitignore`
   - `scripts/report-local-diff.sh`

## Example Commands (for next slices)

```bash
# 0) verify clean selection
git status --short

# 1) CI/auth hardening
git add scripts/check-v2-contract.sh scripts/summarize-v2-contract.sh requirements-dev.txt \
  tests/test_v2_contract_summary_tool.py
git commit -m "fix(ci-v2): auth and artifact hardening"

# 2) deploy template validator hardening
git add scripts/validate-deploy-templates.sh
git commit -m "fix(deploy-validation): syntax-only host-agnostic checks"

# 3) CI de-duplication
git add .github/workflows/ci.yml .github/workflows/integration.yml scripts/run-v2-ci-postchecks.sh
git commit -m "ci(v2): consolidate duplicated post-check steps"

# 4) docs and hygiene
git add docs/V2_RUNBOOK.md docs/V2_IMPLEMENTATION_STATUS.md CHANGELOG.md .gitignore \
  scripts/report-local-diff.sh
git commit -m "docs(v2-ops): runbook/status and hygiene updates"
```

## Final Validation

```bash
.venv/bin/pytest -q tests
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/run-v2-preflight.sh
```
