# TODO (v2 Migration)

## Code Migration Completion (Priority)

### P0 (Blocking)

- [x] Define "v2 migration complete" as code-level acceptance criteria in this repository:
  - v2 route contract (`docs/contract/v2.json`) matches runtime (`GET /api/v2/system/routes`)
  - v2 scaffold tests are required green in CI (`tests/test_v2_scaffold.py`)
  - default startup path remains v2 (`docker-compose.yml`, README quick start)
- [x] Decide the fate of the legacy runtime entrypoint (`run_app.py`):
  - either deprecate/remove it, or explicitly mark it as legacy-only
  - ensure tests/docs are consistent with that decision

### P1 (Important)

- [ ] Classify v1-specific tests as legacy scope and separate from v2 required gates:
  - `tests/test_app.py`
  - v1 import checks in `tests/test_installation.py`
- [ ] Align integration checks and wording to v2-first behavior:
  - remove stale v1 references/comments where practical
  - ensure smoke checks target `/api/v2/*` and `/v2`
- [ ] Isolate unrelated local edits from v2 migration changes.
- [ ] Reduce duplicated v2 post-check logic across CI workflows.

### P2 (Nice to have)

- [ ] Replace low-value lint suppressions with structural fixes where practical.

## Operational Readiness (Non-blocking for code migration)

- [ ] Run a staging cutover rehearsal using `docs/env/v2-cutover-staging.env.example`.
- [ ] Execute `./scripts/run-v2-preflight.sh` and archive cutover artifacts:
  - `.artifacts/v2_contract_diff.json`
  - `.artifacts/v2_readiness.json`
  - `.artifacts/v2_locks.json`
  - `.artifacts/v2_cutover_eval.json`
- [ ] Confirm cutover evaluation result is `decision=GO`.
- [ ] Finalize production thresholds for:
  - `V2_CUTOVER_MAX_QUEUED`
  - `V2_CUTOVER_MAX_RUNNING`
  - `V2_CUTOVER_MAX_FAILED`
  - `V2_CUTOVER_MAX_LOCKED`
- [ ] Document final threshold values in:
  - `docs/env/v2-cutover-staging.env.example`
  - `docs/env/v2-cutover-production.env.example`
  - `docs/V2_RUNBOOK.md`
- [ ] Finalize lock release operation policy (`POST /api/v2/system/locks/release`):
  - execution authority
  - approval flow
  - audit log retention
- [ ] Prepare a one-page cutover and rollback runbook for release day.
- [ ] Pre-assign operators for:
  - API health watch
  - lock queue watch
  - rollback execution
- [ ] Run a dry run and store timestamped logs.
