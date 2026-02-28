# V2 Commit Split Plan

This document proposes a clean commit order for branch `codex/reimpl-scaffold`.

## Preconditions

- Exclude generated files from commits:
  - `.artifacts/*`
  - `nw_diff_v2.db`
- Verify tests before each commit:
  - `.venv/bin/pytest -q tests`

## Recommended Commit Order

1. `feat(v2-core): add FastAPI v2 scaffold and task/capture/compare/export APIs`
   - `src/nw_diff_v2/**`
   - `tests/test_v2_scaffold.py`

2. `feat(v2-ops): add contract/readiness/locks/cutover tooling`
   - `scripts/check-v2-contract.sh`
   - `scripts/check-v2-readiness.py`
   - `scripts/check-v2-locks.py`
   - `scripts/generate-v2-contract.py`
   - `scripts/diff-v2-contract.py`
   - `scripts/evaluate-v2-cutover.py`
   - `scripts/render-v2-cutover-message.py`
   - `scripts/summarize-v2-contract.sh`
   - `scripts/run-v2-preflight.sh`
   - `tests/test_v2_contract_tools.py`
   - `tests/test_v2_readiness_tool.py`
   - `tests/test_v2_lock_tool.py`
   - `tests/test_v2_cutover_tool.py`
   - `tests/test_v2_cutover_message_tool.py`

3. `feat(v2-deploy): add deploy templates and validation`
   - `docs/deploy/**`
   - `scripts/validate-deploy-templates.sh`
   - `tests/test_deploy_template_validate_tool.py`

4. `ci(v2): integrate v2 contract/readiness/locks/cutover checks`
   - `.github/workflows/ci.yml`
   - `.github/workflows/integration.yml`

5. `docs(v2): add migration/runbook/checklist/status and contract snapshot`
   - `docs/V2_MIGRATION.md`
   - `docs/V2_RUNBOOK.md`
   - `docs/V2_CUTOVER_CHECKLIST.md`
   - `docs/V2_IMPLEMENTATION_STATUS.md`
   - `docs/contract/v2.json`
   - `README.md`
   - `.env.example`

6. `chore: ignore generated v2 artifacts`
   - `.gitignore`

## Example Commands

```bash
# 0) verify clean selection
git status --short

# 1) v2 core
git add src/nw_diff_v2 tests/test_v2_scaffold.py
git commit -m "feat(v2-core): add FastAPI v2 scaffold and task/capture/compare/export APIs"

# 2) ops tooling
git add scripts/check-v2-contract.sh scripts/check-v2-readiness.py scripts/check-v2-locks.py \
  scripts/generate-v2-contract.py scripts/diff-v2-contract.py scripts/evaluate-v2-cutover.py \
  scripts/render-v2-cutover-message.py scripts/summarize-v2-contract.sh scripts/run-v2-preflight.sh \
  tests/test_v2_contract_tools.py tests/test_v2_readiness_tool.py tests/test_v2_lock_tool.py \
  tests/test_v2_cutover_tool.py tests/test_v2_cutover_message_tool.py
git commit -m "feat(v2-ops): add contract/readiness/locks/cutover tooling"

# 3) deploy templates
git add docs/deploy scripts/validate-deploy-templates.sh tests/test_deploy_template_validate_tool.py
git commit -m "feat(v2-deploy): add deploy templates and validation"

# 4) CI wiring
git add .github/workflows/ci.yml .github/workflows/integration.yml
git commit -m "ci(v2): integrate v2 contract/readiness/locks/cutover checks"

# 5) docs
git add docs/V2_MIGRATION.md docs/V2_RUNBOOK.md docs/V2_CUTOVER_CHECKLIST.md \
  docs/V2_IMPLEMENTATION_STATUS.md docs/contract/v2.json README.md .env.example
git commit -m "docs(v2): add migration/runbook/checklist/status and contract snapshot"

# 6) ignore generated artifacts
git add .gitignore
git commit -m "chore: ignore generated v2 artifacts"
```

## Final Validation

```bash
.venv/bin/pytest -q tests
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/run-v2-preflight.sh
```
