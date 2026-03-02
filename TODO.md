# TODO (v2 Migration)

## High Priority

- [ ] Run a staging cutover rehearsal using `docs/env/v2-cutover-staging.env.example`.
- [ ] Execute `./scripts/run-v2-preflight.sh` and archive cutover artifacts:
  - `.artifacts/v2_contract_diff.json`
  - `.artifacts/v2_readiness.json`
  - `.artifacts/v2_locks.json`
  - `.artifacts/v2_cutover_eval.json`
- [ ] Confirm cutover evaluation result is `decision=GO`.

## Operational Readiness

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

## Cutover Execution

- [ ] Prepare a one-page cutover and rollback runbook for release day.
- [ ] Pre-assign operators for:
  - API health watch
  - lock queue watch
  - rollback execution
- [ ] Run a dry run and store timestamped logs.

## Repository Hygiene

- [ ] Isolate unrelated local edits from v2 migration changes.
- [ ] Reduce duplicated v2 post-check logic across CI workflows.
- [ ] Replace low-value lint suppressions with structural fixes where practical.
