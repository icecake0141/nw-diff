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

- [x] Classify v1-specific tests as legacy scope and separate from v2 required gates:
  - `tests/test_app.py`
  - v1 import checks in `tests/test_installation.py`
- [x] Align integration checks and wording to v2-first behavior:
  - remove stale v1 references/comments where practical
  - ensure smoke checks target `/api/v2/*` and `/v2`
- [x] Isolate unrelated local edits from v2 migration changes.
- [x] Reduce duplicated v2 post-check logic across CI workflows.

### P2 (Nice to have)

- [x] Replace low-value lint suppressions with structural fixes where practical.

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

## V1 Removal Plan (Breaking Change Track)

### Phase 1: Discovery and Scope

- [x] Inventory all v1 references and dependencies in code/tests/docs:
  - `src/nw_diff/*`
  - `run_app.py`
  - `tests/test_app.py`
  - `tests/test_installation.py` legacy v1 checks
  - docs mentioning v1/legacy runtime
- [x] Define explicit removal scope:
  - files/modules to delete
  - any compatibility stubs to keep temporarily (or none)

### Phase 2: CI and Test Cutover

- [x] Remove legacy v1 test scope from CI:
  - drop `pytest -m "legacy_v1"` job in `.github/workflows/ci.yml`
- [x] Remove or rewrite v1-specific tests to v2-only behavior.
- [x] Ensure required checks are green without any v1 code path.

### Phase 3: Code and Runtime Deletion

- [x] Remove v1 runtime entrypoint (`run_app.py`).
- [x] Remove v1 Flask package (`src/nw_diff/*`) and v1-only templates/assets.
- [x] Remove v1-only scripts or references that are no longer used.

### Phase 4: Documentation and Release Notes

- [x] Update README/docs to state v2-only runtime.
- [x] Add migration note for users still invoking v1 paths.
- [x] Document breaking-change release notes (what was removed, expected replacement paths).

### Phase 5: Final Validation

- [ ] Run full quality gates:
  - `pytest -q tests`
  - `pylint src tests`
  - `mypy src tests`
  - `./scripts/check-v2-migration-complete.sh`
  - integration workflow equivalent checks
- [ ] Confirm no references to removed v1 modules remain in repository.
