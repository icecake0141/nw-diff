# NW-Diff Specification (Current)

## Scope

This document summarizes the current behavior expected by operators and integrators.
The authoritative API route snapshot is `docs/contract/v2.json`.

## Runtime Model

- Default runtime: v2 FastAPI (`src/nw_diff_v2`)
- Legacy runtime: v1 Flask (`src/nw_diff`)
- Default container startup: `docker-compose.yml` -> `uvicorn nw_diff_v2.main:app`

## Core Functional Areas

- Device inventory loading from `hosts.csv`
- Capture task creation and queue execution
- Task status, cancellation, retry, and stream
- File comparison and host-level diff views
- Export endpoints (JSON / HTML)
- System health/readiness/locks introspection

## v2 Endpoint Surface

See full contract in `docs/contract/v2.json`.
Representative routes:

- `POST /api/v2/captures`
- `GET /api/v2/tasks/{task_id}`
- `POST /api/v2/tasks/{task_id}/cancel`
- `POST /api/v2/tasks/{task_id}/retry`
- `GET /api/v2/diff/{hostname}`
- `GET /api/v2/hosts/{hostname}/detail`
- `GET /api/v2/exports/{hostname}`
- `GET /api/v2/system/health`
- `GET /api/v2/system/readiness`
- `GET /api/v2/system/locks`

## Security and Runtime Constraints

- `DEVICE_PASSWORD` is required.
- In non-development environments (`NW_DIFF_ENV` not in `dev/development/local/test`), `NW_DIFF_API_TOKEN` is required.
- v2 task persistence is SQLite-based by design.
- Host-level locking prevents same-host concurrent capture.

## Related Detailed Docs

- Migration: `docs/V2_MIGRATION.md`
- Runbook: `docs/V2_RUNBOOK.md`
- Cutover checklist: `docs/V2_CUTOVER_CHECKLIST.md`
- Implementation status: `docs/V2_IMPLEMENTATION_STATUS.md`
