# NW-Diff v2 Cutover Checklist

## Go/No-Go Gates

1. Test gate:
   - `pytest` green on target branch.
2. Contract gate:
   - `scripts/diff-v2-contract.py --fail-on-diff` passes.
3. Runtime gate:
   - `GET /api/v2/system/health` returns `status=ok`.
   - `GET /api/v2/system/readiness` returns `status=ok`.
4. Queue gate:
   - queued tasks <= agreed threshold.
   - running tasks <= agreed threshold.
   - locked host count <= agreed threshold.
5. Error gate:
   - failed task count within agreed threshold.
6. Security gate:
   - production auth configuration validated.
   - reverse proxy and TLS settings validated.
7. Deploy template gate:
   - `deploy_template_validation.json` reports `status=ok`.

## Execution Steps

1. Freeze:
   - Stop non-essential config changes.
2. Verify pre-cutover gates:
   - Run contract/readiness checks.
   - Load threshold profile:
     - staging: `docs/env/v2-cutover-staging.env.example`
     - production: `docs/env/v2-cutover-production.env.example`
   - Ensure `V2_CUTOVER_MAX_LOCKED` is explicitly set for target environment.
3. Switch traffic:
   - Route API/UI to v2 endpoints.
   - Apply nginx cutover template changes:
     - `docs/deploy/nginx-v1-v2-cutover.conf.example`
4. Observe:
   - Monitor health/readiness/worker/logs.
   - If lock conflict persists, inspect `/api/v2/system/locks` and only then run cleanup/release.
5. Confirm:
   - Validate capture, diff, export, retry paths.

## Rollback Triggers

1. Readiness remains degraded.
2. Contract mismatch detected after deploy.
3. Critical capture failure rate spike.
4. API error rate or latency breach.

## Rollback Steps

1. Re-point traffic to v1.
2. Keep v2 artifacts/DB for postmortem.
3. Collect:
   - `v2_contract.json`
   - `v2_contract_diff.json`
   - `v2_readiness.json`
   - `v2_locks.json`
   - `v2_cutover_eval.json`
4. Create incident report and remediation tasks.
