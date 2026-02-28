# NW-Diff v2 Migration Guide

This guide describes a practical migration from current Flask-based v1 routes to
the new FastAPI-based v2 scaffold under `src/nw_diff_v2/`.

## Scope

- v2 currently focuses on API-first operation.
- Task persistence is SQLite-only (`sqlite:///...`) by design.
- PostgreSQL support is intentionally out of scope.

## Current v2 Endpoints

- `POST /api/v2/captures`
- `GET /api/v2/tasks/{task_id}`
- `POST /api/v2/tasks/{task_id}/cancel`
- `POST /api/v2/tasks/{task_id}/retry`
- `GET /api/v2/tasks/{task_id}/stream?tail_lines=20`
  - supports resume via `Last-Event-ID`
- `POST /api/v2/compare/files`
- `GET /api/v2/diff/{hostname}?view=inline|sidebyside`
- `GET /api/v2/hosts/{hostname}/detail?view=inline|sidebyside`
- `GET /api/v2/hosts/summary?limit=50&host_contains=router&prioritize_failed=true`
- `GET /api/v2/logs?source=app|task&limit=1000&contains=...`
- `GET /api/v2/exports/{hostname}`
- `GET /api/v2/exports/{hostname}/diff-json`
- `GET /api/v2/exports/{hostname}/html`
- `GET /api/v2/system/worker`
- `GET /api/v2/system/health`
- `GET /api/v2/system/readiness`
- `GET /api/v2/system/locks`
- `POST /api/v2/system/locks/cleanup`
- `POST /api/v2/system/locks/release`
- `GET /api/v2/system/routes`
- `GET /api/v2/system/contract`
- `GET /v2` (minimal operational UI)
- `GET /v2/hosts/{hostname}` (host detail UI)
- `GET /v2/logs` (logs UI)

## Environment Variables

- `NW_DIFF_ENV` (`development` by default)
- `DEVICE_PASSWORD` (required)
- `NW_DIFF_API_TOKEN` (required outside development)
- Optional Basic fallback:
  - `NW_DIFF_BASIC_USER`
  - `NW_DIFF_BASIC_PASSWORD` or `NW_DIFF_BASIC_PASSWORD_HASH`
- `HOSTS_CSV` equivalent in v2: `hosts_csv` setting (default: `hosts.csv`)
- `hosts.csv` rows are validated before use:
  - host/user/model allowed-character checks
  - IP address validation
  - port range check (`1-65535`)
  - field length caps (host/user/model)
- SQLite path: `db_url` (default: `sqlite:///./nw_diff_v2.db`)
- Batch lock handling: `batch_conflict_policy`:
  - `all_or_nothing` (default)
  - `skip_locked`
- Lock expiration: `host_lock_timeout_seconds`
- Host locks are persisted in the same SQLite DB (`host_locks` table)
- Concurrency rule:
  - Same host cannot run concurrent captures
  - Different hosts can be captured in parallel
- Readiness thresholds:
  - `readiness_max_queued`
  - `readiness_max_running`
  - `readiness_max_locked`
- Background worker:
  - `task_worker_enabled` (default: true)
  - `task_worker_threads` (default: 1)
  - `task_worker_poll_seconds` (default: 0.5)
- Startup recovery marks orphaned `running` tasks as `failed`.
- Cancel endpoint returns `409` for terminal states (`completed`/`failed`/`cancelled`).

## Migration Phases

1. Parallel run
- Keep v1 as primary.
- Start v2 on a separate path/port.
- Optionally run queue worker as a separate process:
  - `python -m nw_diff_v2.worker`
- Validate capture flow via `POST /api/v2/captures`.

2. API client cutover
- Point automation clients to v2 capture/task endpoints.
- Keep v1 UI for visual diff until v2 UI is implemented.

3. Export cutover
- Move machine-readable export consumers to `GET /api/v2/exports/{hostname}`.

4. Final switch
- Switch reverse proxy to v2 APIs.
- Keep v1 routes available during rollback window.

## Rollback

- Keep v1 runtime config and data paths unchanged.
- Re-point clients/proxy to v1 endpoints.
- v2 artifacts and SQLite DB are isolated and can remain for postmortem.

## Contract Snapshot

- Route contract snapshot is tracked at `docs/contract/v2.json`.
- Regenerate with: `python scripts/generate-v2-contract.py --output docs/contract/v2.json`
- Operational procedures: `docs/V2_RUNBOOK.md`.
- Cutover gates/checklist: `docs/V2_CUTOVER_CHECKLIST.md`.
- Cutover threshold env vars:
  - `V2_CUTOVER_MAX_QUEUED`
  - `V2_CUTOVER_MAX_RUNNING`
  - `V2_CUTOVER_MAX_FAILED`
  - `V2_CUTOVER_MAX_LOCKED`
- Threshold templates:
  - `docs/env/v2-cutover-staging.env.example`
  - `docs/env/v2-cutover-production.env.example`
- nginx deploy templates:
  - `docs/deploy/nginx-v2.conf.example`
  - `docs/deploy/nginx-v1-v2-cutover.conf.example`
