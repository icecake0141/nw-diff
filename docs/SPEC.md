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

## 日本語訳

## スコープ

このドキュメントは、運用者および連携開発者向けに現在の期待動作を要約したものです。  
API ルート定義の正本は `docs/contract/v2.json` です。

## ランタイムモデル

- 標準ランタイム: v2 FastAPI（`src/nw_diff_v2`）
- 旧ランタイム: v1 Flask（`src/nw_diff`）
- コンテナ標準起動: `docker-compose.yml` -> `uvicorn nw_diff_v2.main:app`

## 主要機能領域

- `hosts.csv` からのデバイスインベントリ読込
- キャプチャタスク作成とキュー実行
- タスク状態確認、キャンセル、リトライ、ストリーム
- ファイル比較とホスト単位の差分表示
- エクスポート API（JSON / HTML）
- ヘルス、readiness、locks などのシステム確認

## v2 エンドポイント一覧

全ルートは `docs/contract/v2.json` を参照してください。  
代表的なルート:

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

## セキュリティ/ランタイム制約

- `DEVICE_PASSWORD` は必須です。
- 非開発環境（`NW_DIFF_ENV` が `dev/development/local/test` 以外）では `NW_DIFF_API_TOKEN` が必須です。
- v2 のタスク永続化は設計上 SQLite ベースです。
- 同一ホストへの同時キャプチャはホストロックにより防止されます。

## 関連ドキュメント

- 移行: `docs/V2_MIGRATION.md`
- ランブック: `docs/V2_RUNBOOK.md`
- 切替チェックリスト: `docs/V2_CUTOVER_CHECKLIST.md`
- 実装ステータス: `docs/V2_IMPLEMENTATION_STATUS.md`
