# NW-Diff v2 Migration Guide

This guide documents the migration that moved NW-Diff from Flask-based v1 routes
to the FastAPI-based v2 runtime under `src/nw_diff_v2/`.

## Current Status (v1 Removed)

- v1 runtime (`src/nw_diff`) is removed.
- v1 entrypoint (`run_app.py`) is removed.
- Use v2 startup command:
  - `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src`
- Use v2 endpoints:
  - UI: `/v2`
  - API: `/api/v2/*`

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

## Migration Phases (Historical Record)

1. Parallel run
- Keep v1 as primary (at that time).
- Start v2 on a separate path/port.
- Optionally run queue worker as a separate process:
  - `python -m nw_diff_v2.worker`
- Validate capture flow via `POST /api/v2/captures`.

2. API client cutover
- Point automation clients to v2 capture/task endpoints.
- Keep v1 UI for visual diff until v2 UI is implemented (at that time).

3. Export cutover
- Move machine-readable export consumers to `GET /api/v2/exports/{hostname}`.

4. Final switch
- Switch reverse proxy to v2 APIs.
- Keep v1 routes available during rollback window (temporary).

## Rollback

The old rollback path to v1 is no longer available after v1 removal.

- Keep backups of v2 runtime config and SQLite data for recovery.
- Re-deploy a known-good v2 release if rollback is required.
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
  - `docs/deploy/nginx-v1-v2-cutover.conf.example` (historical reference)

## 日本語訳

# NW-Diff v2 移行ガイド

このガイドは、Flask ベース v1 ルートから
`src/nw_diff_v2/` 配下の FastAPI ベース v2 ランタイムへ移行した内容を記録したものです。

## 現在の状態（v1 削除済み）

- v1 ランタイム（`src/nw_diff`）は削除済みです。
- v1 エントリポイント（`run_app.py`）は削除済みです。
- v2 の起動コマンド:
  - `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src`
- v2 のエンドポイント:
  - UI: `/v2`
  - API: `/api/v2/*`

## スコープ

- v2 は現在 API ファースト運用を主眼としています。
- タスク永続化は設計上 SQLite のみ（`sqlite:///...`）です。
- PostgreSQL サポートは意図的に対象外です。

## 現在の v2 エンドポイント

- `POST /api/v2/captures`
- `GET /api/v2/tasks/{task_id}`
- `POST /api/v2/tasks/{task_id}/cancel`
- `POST /api/v2/tasks/{task_id}/retry`
- `GET /api/v2/tasks/{task_id}/stream?tail_lines=20`
  - `Last-Event-ID` による再開をサポート
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
- `GET /v2`（最小運用 UI）
- `GET /v2/hosts/{hostname}`（ホスト詳細 UI）
- `GET /v2/logs`（ログ UI）

## 環境変数

- `NW_DIFF_ENV`（デフォルト `development`）
- `DEVICE_PASSWORD`（必須）
- `NW_DIFF_API_TOKEN`（development 以外で必須）
- 任意の Basic フォールバック:
  - `NW_DIFF_BASIC_USER`
  - `NW_DIFF_BASIC_PASSWORD` または `NW_DIFF_BASIC_PASSWORD_HASH`
- v2 での `HOSTS_CSV` 相当: `hosts_csv` 設定（デフォルト `hosts.csv`）
- `hosts.csv` 行は利用前に検証:
  - host/user/model の許容文字チェック
  - IP アドレス検証
  - ポート範囲チェック（`1-65535`）
  - フィールド長上限（host/user/model）
- SQLite パス: `db_url`（デフォルト `sqlite:///./nw_diff_v2.db`）
- バッチロック処理: `batch_conflict_policy`:
  - `all_or_nothing`（デフォルト）
  - `skip_locked`
- ロック有効期限: `host_lock_timeout_seconds`
- ホストロックは同一 SQLite DB の `host_locks` テーブルに永続化
- 同時実行ルール:
  - 同一ホストの同時 capture は不可
  - 異なるホストは並列 capture 可能
- Readiness 閾値:
  - `readiness_max_queued`
  - `readiness_max_running`
  - `readiness_max_locked`
- バックグラウンド worker:
  - `task_worker_enabled`（デフォルト true）
  - `task_worker_threads`（デフォルト 1）
  - `task_worker_poll_seconds`（デフォルト 0.5）
- 起動時リカバリーで孤立した `running` タスクを `failed` に変更
- cancel エンドポイントは終端状態（`completed`/`failed`/`cancelled`）に `409` を返す

## 移行フェーズ（履歴）

1. 並行稼働
- （当時）v1 を主系として維持。
- v2 を別パス/ポートで起動。
- 必要に応じ queue worker を別プロセスで実行:
  - `python -m nw_diff_v2.worker`
- `POST /api/v2/captures` で capture フローを検証。

2. API クライアント切替
- 自動化クライアントを v2 capture/task エンドポイントへ切替。
- （当時）v2 UI 実装完了までは v1 UI の可視差分を維持。

3. エクスポート切替
- 機械可読エクスポート利用側を `GET /api/v2/exports/{hostname}` へ移行。

4. 最終切替
- リバースプロキシを v2 API へ切替。
- （当時）ロールバック期間中は v1 ルートを維持。

## ロールバック

v1 削除後は、旧 v1 へのロールバックはできません。

- 復旧時は v2 の設定バックアップと SQLite データを利用します。
- ロールバックが必要な場合は、正常実績のある v2 リリースを再デプロイします。
- v2 アーティファクトと SQLite DB は隔離されているため、事後検証用に保持可能です。

## 契約スナップショット

- ルート契約スナップショットは `docs/contract/v2.json` で管理。
- 再生成: `python scripts/generate-v2-contract.py --output docs/contract/v2.json`
- 運用手順: `docs/V2_RUNBOOK.md`。
- 切替ゲート/チェックリスト: `docs/V2_CUTOVER_CHECKLIST.md`。
- 切替閾値の環境変数:
  - `V2_CUTOVER_MAX_QUEUED`
  - `V2_CUTOVER_MAX_RUNNING`
  - `V2_CUTOVER_MAX_FAILED`
  - `V2_CUTOVER_MAX_LOCKED`
- 閾値テンプレート:
  - `docs/env/v2-cutover-staging.env.example`
  - `docs/env/v2-cutover-production.env.example`
- nginx デプロイテンプレート:
  - `docs/deploy/nginx-v2.conf.example`
  - `docs/deploy/nginx-v1-v2-cutover.conf.example`（履歴参照）
