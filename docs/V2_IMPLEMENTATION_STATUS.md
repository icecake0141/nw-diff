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

- Run staging cutover rehearsal using environment profile:
  - `docs/env/v2-cutover-staging.env.example`
- Validate release workflow in CI after merge (artifact + summary outputs).
- Finalize operator runbook for lock-release authority and audit process.
- Prepare production cutover window and rollback drill execution log.
