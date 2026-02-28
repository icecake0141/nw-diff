# Deploy Templates

This directory provides deployment templates for NW-Diff v2.

## Files

- `nw-diff-v2-api.service.example`
  - systemd unit for v2 API (`uvicorn`)
- `nw-diff-v2-worker.service.example`
  - systemd unit for external v2 worker
- `nginx-v2.conf.example`
  - nginx reverse proxy for v2-only deployments
- `nginx-v1-v2-cutover.conf.example`
  - nginx staged cutover template for v1 -> v2 migration

## Validation

After applying nginx templates:

1. `nginx -t`
2. `systemctl reload nginx`
3. Validate:
   - `/health`
   - `/api/v2/system/health`
   - `/api/v2/system/readiness`

Automated template validation:

- `./scripts/validate-deploy-templates.sh`
- strict mode (CI): `./scripts/validate-deploy-templates.sh --strict`
- write markdown summary:
  - `SUMMARY_PATH=/tmp/deploy_template_summary.md ./scripts/validate-deploy-templates.sh`
- write machine-readable JSON:
  - `JSON_OUTPUT=/tmp/deploy_template_validation.json ./scripts/validate-deploy-templates.sh`
