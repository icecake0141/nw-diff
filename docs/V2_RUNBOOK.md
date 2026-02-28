# NW-Diff v2 Runbook

## Purpose

Operational procedures for running and troubleshooting NW-Diff v2.

## Startup

1. API:
   - `export DEVICE_PASSWORD=...`
   - `export NW_DIFF_ENV=production`
   - `uvicorn nw_diff_v2.main:app --host 0.0.0.0 --port 8000 --app-dir src`
2. Optional external worker:
   - `python -m nw_diff_v2.worker`
3. systemd examples:
   - API: `docs/deploy/nw-diff-v2-api.service.example`
   - Worker: `docs/deploy/nw-diff-v2-worker.service.example`
4. nginx examples:
   - v2-only: `docs/deploy/nginx-v2.conf.example`
   - staged cutover: `docs/deploy/nginx-v1-v2-cutover.conf.example`

## Core Health Checks

1. `GET /api/v2/system/health`
   - Basic API + DB readiness.
2. `GET /api/v2/system/readiness`
   - Contract sanity + queue/running thresholds.
3. `GET /api/v2/system/contract`
   - Required route contract status.
4. `GET /api/v2/system/worker`
   - Task status counters.
5. `GET /api/v2/system/locks`
   - Active host lock rows (`host`, `age_seconds`, `is_stale`, `owner_task_ids`).
6. `POST /api/v2/system/locks/cleanup`
   - Deletes stale host lock rows based on `host_lock_timeout_seconds`.
7. `POST /api/v2/system/locks/release`
   - Force-releases specific hosts from lock table.
   - Request body: `{"hosts": ["router1", "router2"]}`
   - Response fields: `released` (actually removed), `not_locked` (already absent), `remaining`.
   - Returns `400` on empty list or invalid hostnames.

## Contract Operations

1. Generate snapshot:
   - `python scripts/generate-v2-contract.py --output docs/contract/v2.json`
2. Check current vs snapshot:
   - `python scripts/generate-v2-contract.py --output .artifacts/v2_contract_current.json`
   - `python scripts/diff-v2-contract.py --baseline docs/contract/v2.json --candidate .artifacts/v2_contract_current.json --fail-on-diff`
3. Smoke check endpoint contract:
   - `./scripts/check-v2-contract.sh`
4. Full preflight gate:
   - `./scripts/run-v2-preflight.sh`
   - Runs contract + readiness + locks + deploy template validation + cutover + message in one pass.
   - Set `DEPLOY_VALIDATION_STRICT=true` when host has `nginx`/`systemd-analyze`.
5. Readiness CLI check:
   - `python scripts/check-v2-readiness.py --url http://127.0.0.1:18080/api/v2/system/readiness`
6. Lock CLI check:
   - `python scripts/check-v2-locks.py --url http://127.0.0.1:18080/api/v2/system/locks --max-locks 100`
   - Add `--allow-stale` for informational mode.
7. Cutover decision CLI:
   - `python scripts/evaluate-v2-cutover.py --readiness-file .artifacts/v2_readiness.json --contract-diff-file .artifacts/v2_contract_diff.json --deploy-validation-file .artifacts/deploy_template_validation.json`
   - thresholds via env:
     - `V2_CUTOVER_MAX_QUEUED`
     - `V2_CUTOVER_MAX_RUNNING`
     - `V2_CUTOVER_MAX_FAILED`
     - `V2_CUTOVER_MAX_LOCKED`
   - example profiles:
     - `docs/env/v2-cutover-staging.env.example`
     - `docs/env/v2-cutover-production.env.example`
6. Notification message rendering:
   - `python scripts/render-v2-cutover-message.py --input .artifacts/v2_cutover_eval.json --format markdown --output .artifacts/v2_cutover_message.md`

## Incident Triage

1. Readiness degraded:
   - Inspect `checks` in `/api/v2/system/readiness`.
   - If `queue_depth` failed, scale worker or reduce incoming load.
   - If `lock_depth` failed, inspect `/api/v2/system/locks` and release stale lock holders.
   - If `contract` failed, inspect deployment version mismatch.
2. Capture backlog:
   - Check `/api/v2/tasks?status_filter=queued`.
   - Check `/api/v2/system/worker` and worker logs.
3. Host lock conflict:
   - Verify same-host concurrent capture attempts.
   - Inspect `/api/v2/system/locks` for active lock rows.
   - If stale rows remain, run `POST /api/v2/system/locks/cleanup`.
   - If a non-stale orphan lock blocks work, run `POST /api/v2/system/locks/release`.
   - Check stale lock timeout config (`host_lock_timeout_seconds`).

## Logs

1. App logs:
   - `GET /api/v2/logs?source=app&limit=1000`
   - Example filter: `GET /api/v2/logs?source=app&contains=ERROR&limit=200`
2. Task logs:
   - `GET /api/v2/logs?source=task&task_id=<task_id>&limit=1000`
   - Example filter: `GET /api/v2/logs?source=task&task_id=<task_id>&contains=failed`

## Recovery

1. Restart API process.
2. Startup will recover orphaned `running` tasks to `failed`.
3. Startup also runs stale lock cleanup using `host_lock_timeout_seconds`.
4. Retry tasks via:
   - `POST /api/v2/tasks/{task_id}/retry`

## Checklist

- Cutover checklist: `docs/V2_CUTOVER_CHECKLIST.md`
