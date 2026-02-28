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

## 日本語訳

# NW-Diff v2 切替チェックリスト

## Go/No-Go 判定ゲート

1. テストゲート:
   - 対象ブランチで `pytest` がすべて成功。
2. 契約ゲート:
   - `scripts/diff-v2-contract.py --fail-on-diff` が成功。
3. ランタイムゲート:
   - `GET /api/v2/system/health` が `status=ok` を返す。
   - `GET /api/v2/system/readiness` が `status=ok` を返す。
4. キューゲート:
   - queued タスク数が合意閾値以下。
   - running タスク数が合意閾値以下。
   - ロック中ホスト数が合意閾値以下。
5. エラーゲート:
   - failed タスク数が合意閾値内。
6. セキュリティゲート:
   - 本番認証設定が検証済み。
   - リバースプロキシと TLS 設定が検証済み。
7. デプロイテンプレートゲート:
   - `deploy_template_validation.json` が `status=ok` を報告。

## 実施手順

1. フリーズ:
   - 非必須の設定変更を停止。
2. 切替前ゲート確認:
   - contract/readiness チェックを実行。
   - 閾値プロファイルを読み込み:
     - staging: `docs/env/v2-cutover-staging.env.example`
     - production: `docs/env/v2-cutover-production.env.example`
   - 対象環境で `V2_CUTOVER_MAX_LOCKED` が明示設定されていることを確認。
3. トラフィック切替:
   - API/UI を v2 エンドポイントへルーティング。
   - nginx 切替テンプレート変更を適用:
     - `docs/deploy/nginx-v1-v2-cutover.conf.example`
4. 観測:
   - health/readiness/worker/logs を監視。
   - ロック競合が継続する場合は `/api/v2/system/locks` を確認し、その後に cleanup/release を実行。
5. 確認:
   - capture、diff、export、retry の経路を検証。

## ロールバックトリガー

1. Readiness の劣化が継続する。
2. デプロイ後に契約不一致を検出。
3. 重大なキャプチャ失敗率が急増。
4. API エラー率またはレイテンシが閾値超過。

## ロールバック手順

1. トラフィックを v1 に戻す。
2. 事後検証用に v2 アーティファクト/DB は保持。
3. 以下を収集:
   - `v2_contract.json`
   - `v2_contract_diff.json`
   - `v2_readiness.json`
   - `v2_locks.json`
   - `v2_cutover_eval.json`
4. インシデントレポートと改善タスクを作成。
