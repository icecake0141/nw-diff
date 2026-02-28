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

## Authentication Policy

1. API endpoints under `/api/v2/*` require authentication.
2. Preferred mode in CI/operations:
   - Bearer token via `NW_DIFF_API_TOKEN`
   - Example header: `Authorization: Bearer <token>`
3. Optional mode:
   - Basic auth via `NW_DIFF_BASIC_USER` and `NW_DIFF_BASIC_PASSWORD` or hash variant.
4. Development bypass:
   - only when `NW_DIFF_ENV` is development-like and `NW_DIFF_API_TOKEN` is unset.
   - Never rely on this behavior in staging/production.

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
   - Uses auth automatically:
     - bearer when `NW_DIFF_API_TOKEN` is set
     - basic auth when `NW_DIFF_BASIC_USER` and `NW_DIFF_BASIC_PASSWORD` are set
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

## CI Behavior Notes

1. Deploy template validation in CI is syntax-only:
   - nginx template checks do not require real cert files or privileged ports.
   - systemd unit checks do not require real venv executables.
2. v2 cutover/readiness helper steps are resilient to missing artifacts:
   - `--allow-missing` is used in CI follow-up steps to avoid cascade failures.
3. `scripts/summarize-v2-contract.sh` tolerates malformed/missing artifact JSON and writes summary diagnostics instead of failing the job.

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

## 日本語訳

# NW-Diff v2 ランブック

## 目的

NW-Diff v2 の運用およびトラブルシューティング手順。

## 起動

1. API:
   - `export DEVICE_PASSWORD=...`
   - `export NW_DIFF_ENV=production`
   - `uvicorn nw_diff_v2.main:app --host 0.0.0.0 --port 8000 --app-dir src`
2. 任意の外部 worker:
   - `python -m nw_diff_v2.worker`
3. systemd 例:
   - API: `docs/deploy/nw-diff-v2-api.service.example`
   - Worker: `docs/deploy/nw-diff-v2-worker.service.example`
4. nginx 例:
   - v2 専用: `docs/deploy/nginx-v2.conf.example`
   - 段階切替: `docs/deploy/nginx-v1-v2-cutover.conf.example`

## 認証ポリシー

1. `/api/v2/*` 配下の API エンドポイントは認証必須。
2. CI/運用での推奨モード:
   - `NW_DIFF_API_TOKEN` による Bearer トークン
   - ヘッダー例: `Authorization: Bearer <token>`
3. 任意モード:
   - `NW_DIFF_BASIC_USER` と `NW_DIFF_BASIC_PASSWORD`（またはハッシュ）による Basic 認証。
4. 開発バイパス:
   - `NW_DIFF_ENV` が開発系かつ `NW_DIFF_API_TOKEN` 未設定時のみ。
   - staging/production でこの挙動に依存しないこと。

## 主要ヘルスチェック

1. `GET /api/v2/system/health`
   - 基本的な API + DB の生存確認。
2. `GET /api/v2/system/readiness`
   - 契約整合 + queue/running 閾値チェック。
3. `GET /api/v2/system/contract`
   - 必須ルート契約の状態。
4. `GET /api/v2/system/worker`
   - タスク状態カウンター。
5. `GET /api/v2/system/locks`
   - アクティブなホストロック行（`host`, `age_seconds`, `is_stale`, `owner_task_ids`）。
6. `POST /api/v2/system/locks/cleanup`
   - `host_lock_timeout_seconds` に基づき stale host lock 行を削除。
7. `POST /api/v2/system/locks/release`
   - 指定ホストを lock table から強制解放。
   - リクエスト本文: `{"hosts": ["router1", "router2"]}`
   - レスポンス: `released`（実際に削除）、`not_locked`（元から未ロック）、`remaining`。
   - 空配列や不正ホスト名では `400` を返す。

## 契約運用

1. スナップショット生成:
   - `python scripts/generate-v2-contract.py --output docs/contract/v2.json`
2. 現在値とスナップショットを比較:
   - `python scripts/generate-v2-contract.py --output .artifacts/v2_contract_current.json`
   - `python scripts/diff-v2-contract.py --baseline docs/contract/v2.json --candidate .artifacts/v2_contract_current.json --fail-on-diff`
3. エンドポイント契約スモークチェック:
   - `./scripts/check-v2-contract.sh`
   - 認証は自動適用:
     - `NW_DIFF_API_TOKEN` 設定時は bearer
     - `NW_DIFF_BASIC_USER` と `NW_DIFF_BASIC_PASSWORD` 設定時は basic auth
4. フル preflight ゲート:
   - `./scripts/run-v2-preflight.sh`
   - contract + readiness + locks + deploy template validation + cutover + message を一括実行。
   - ホストに `nginx`/`systemd-analyze` がある場合は `DEPLOY_VALIDATION_STRICT=true` を設定。
5. Readiness CLI チェック:
   - `python scripts/check-v2-readiness.py --url http://127.0.0.1:18080/api/v2/system/readiness`
6. Lock CLI チェック:
   - `python scripts/check-v2-locks.py --url http://127.0.0.1:18080/api/v2/system/locks --max-locks 100`
   - 情報目的モードでは `--allow-stale` を追加。
7. Cutover 判定 CLI:
   - `python scripts/evaluate-v2-cutover.py --readiness-file .artifacts/v2_readiness.json --contract-diff-file .artifacts/v2_contract_diff.json --deploy-validation-file .artifacts/deploy_template_validation.json`
   - env で閾値を指定:
     - `V2_CUTOVER_MAX_QUEUED`
     - `V2_CUTOVER_MAX_RUNNING`
     - `V2_CUTOVER_MAX_FAILED`
     - `V2_CUTOVER_MAX_LOCKED`
   - プロファイル例:
     - `docs/env/v2-cutover-staging.env.example`
     - `docs/env/v2-cutover-production.env.example`
6. 通知メッセージ生成:
   - `python scripts/render-v2-cutover-message.py --input .artifacts/v2_cutover_eval.json --format markdown --output .artifacts/v2_cutover_message.md`

## CI 挙動メモ

1. CI 上の deploy template validation は構文チェックのみ:
   - nginx テンプレート検証で実証明書や特権ポートは不要。
   - systemd unit 検証で実 venv 実行ファイルは不要。
2. v2 cutover/readiness 補助手順はアーティファクト欠損に耐性あり:
   - CI 後続手順で連鎖失敗を避けるため `--allow-missing` を利用。
3. `scripts/summarize-v2-contract.sh` は不正/欠損 JSON を許容し、ジョブ失敗ではなく診断サマリーを書き出す。

## インシデント一次対応

1. Readiness 劣化:
   - `/api/v2/system/readiness` の `checks` を確認。
   - `queue_depth` 失敗なら worker を増やすか流入を抑制。
   - `lock_depth` 失敗なら `/api/v2/system/locks` を確認し stale lock 保持者を解放。
   - `contract` 失敗ならデプロイ版不一致を確認。
2. Capture 滞留:
   - `/api/v2/tasks?status_filter=queued` を確認。
   - `/api/v2/system/worker` と worker ログを確認。
3. Host lock 競合:
   - 同一ホストへの同時 capture 試行を確認。
   - `/api/v2/system/locks` で有効ロック行を確認。
   - stale 行が残る場合は `POST /api/v2/system/locks/cleanup` を実行。
   - stale でない孤立ロックが作業を阻害する場合は `POST /api/v2/system/locks/release` を実行。
   - stale lock timeout 設定（`host_lock_timeout_seconds`）を確認。

## ログ

1. アプリログ:
   - `GET /api/v2/logs?source=app&limit=1000`
   - 例: `GET /api/v2/logs?source=app&contains=ERROR&limit=200`
2. タスクログ:
   - `GET /api/v2/logs?source=task&task_id=<task_id>&limit=1000`
   - 例: `GET /api/v2/logs?source=task&task_id=<task_id>&contains=failed`

## リカバリー

1. API プロセスを再起動。
2. 起動時に孤立 `running` タスクを `failed` に復旧。
3. 起動時に `host_lock_timeout_seconds` を使って stale lock cleanup も実行。
4. 次でタスク再試行:
   - `POST /api/v2/tasks/{task_id}/retry`

## チェックリスト

- 切替チェックリスト: `docs/V2_CUTOVER_CHECKLIST.md`
