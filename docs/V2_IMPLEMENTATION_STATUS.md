# NW-Diff v2 Implementation Status

Last updated: 2026-02-28

## Completed

- v2 API scaffold under `src/nw_diff_v2` with task/capture/compare/exports/hosts/logs/system endpoints
- v2 minimal UI pages:
  - `/v2`
  - `/v2/hosts/{hostname}`
  - `/v2/logs`
- Host-level locking policy:
  - same-host concurrent capture rejected
  - different-host parallel capture allowed
- Lock operations:
  - `GET /api/v2/system/locks`
  - `POST /api/v2/system/locks/cleanup`
  - `POST /api/v2/system/locks/release`
- Startup recovery:
  - orphaned `running` tasks recovered to `failed`
  - stale locks cleaned on API/worker startup
- Security/runtime policy:
  - `NW_DIFF_API_TOKEN` required outside development-like envs
  - `hosts.csv` validation with safe chars, IP/port checks, length limits
- Contract/readiness/cutover tooling:
  - `scripts/generate-v2-contract.py`
  - `scripts/diff-v2-contract.py`
  - `scripts/check-v2-contract.sh`
  - `scripts/run-v2-preflight.sh`
    - includes deploy template validation gate
  - `scripts/check-v2-readiness.py`
  - `scripts/check-v2-locks.py`
  - `scripts/evaluate-v2-cutover.py`
  - `scripts/render-v2-cutover-message.py`
  - `scripts/summarize-v2-contract.sh`
- CI integration:
  - contract/readiness/locks checks
  - cutover evaluation + message rendering
  - artifacts uploaded from `.artifacts/*`

## Quality Gate Snapshot

- Unit/integration tests in this repository:
  - `pytest -q tests`
  - current result: `268 passed, 3 skipped`
- Local contract smoke:
  - `./scripts/check-v2-contract.sh`
  - current result: passed

## Remaining Work (Operational)

1. Staging cutover rehearsal (must-pass)
   - Use `docs/env/v2-cutover-staging.env.example`
   - Capture artifacts:
     - `.artifacts/v2_contract_diff.json`
     - `.artifacts/v2_readiness.json`
     - `.artifacts/v2_locks.json`
     - `.artifacts/v2_cutover_eval.json`
   - Acceptance:
     - `decision=GO` in cutover evaluation
     - no stale locks remain after rehearsal cleanup

2. Production lock-operation procedure finalization
   - Finalize authority boundary for `POST /api/v2/system/locks/release`
   - Define audit log retention for lock-release operations
   - Acceptance:
     - reviewed and approved in runbook

3. Release/cutover execution pack
   - Prepare one-page rollback checklist and command set
   - Pre-assign operators for:
     - API health watch
     - lock queue watch
     - rollback executor
   - Acceptance:
     - dry-run complete with timestamped log

## Remaining Work (Code/Repo Hygiene)

1. Separate unrelated local edits from v2 track
   - Current mixed local changes include:
     - `requirements.txt`
     - `tests/test_auth_basic.py`
     - `tests/test_docker.py`
   - Use `scripts/report-local-diff.sh` before each commit to keep PR scope isolated.

2. CI workflow de-duplication
   - Shared v2 contract/readiness/cutover steps are duplicated in:
     - `.github/workflows/ci.yml`
     - `.github/workflows/integration.yml`
   - Extract common logic into one script entrypoint and keep workflow files thin.

3. Lint policy cleanup
   - Current test modules use selective pylint disables for CI stability.
   - Replace suppressions with structural fixes where low-cost, then tighten `.pylintrc`.
