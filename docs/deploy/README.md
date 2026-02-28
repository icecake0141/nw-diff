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

## 日本語訳

# デプロイテンプレート

このディレクトリには NW-Diff v2 用のデプロイテンプレートが含まれます。

## ファイル

- `nw-diff-v2-api.service.example`
  - v2 API（`uvicorn`）向け systemd ユニット
- `nw-diff-v2-worker.service.example`
  - 外部 v2 worker 向け systemd ユニット
- `nginx-v2.conf.example`
  - v2 専用デプロイ向け nginx リバースプロキシ設定
- `nginx-v1-v2-cutover.conf.example`
  - v1 -> v2 移行向け段階切替 nginx テンプレート

## 検証

nginx テンプレート適用後:

1. `nginx -t`
2. `systemctl reload nginx`
3. 次を検証:
   - `/health`
   - `/api/v2/system/health`
   - `/api/v2/system/readiness`

自動テンプレート検証:

- `./scripts/validate-deploy-templates.sh`
- strict モード（CI）: `./scripts/validate-deploy-templates.sh --strict`
- Markdown サマリー出力:
  - `SUMMARY_PATH=/tmp/deploy_template_summary.md ./scripts/validate-deploy-templates.sh`
- 機械可読 JSON 出力:
  - `JSON_OUTPUT=/tmp/deploy_template_validation.json ./scripts/validate-deploy-templates.sh`
