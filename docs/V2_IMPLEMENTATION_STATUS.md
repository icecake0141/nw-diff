# NW-Diff v2 Implementation Status

Last updated: 2026-02-28

## Completed

- v2 API scaffold under `src/nw_diff_v2` with task/capture/compare/exports/hosts/logs/system endpoints
- v2 minimal UI pages:
  - `/v2`
  - `/v2/hosts/{hostname}`
  - `/v2/logs`
- Host-level locking policy:
  - same-host concurrent capture rejected
  - different-host parallel capture allowed
- Lock operations:
  - `GET /api/v2/system/locks`
  - `POST /api/v2/system/locks/cleanup`
  - `POST /api/v2/system/locks/release`
- Startup recovery:
  - orphaned `running` tasks recovered to `failed`
  - stale locks cleaned on API/worker startup
- Security/runtime policy:
  - `NW_DIFF_API_TOKEN` required outside development-like envs
  - `hosts.csv` validation with safe chars, IP/port checks, length limits
- Contract/readiness/cutover tooling:
  - `scripts/generate-v2-contract.py`
  - `scripts/diff-v2-contract.py`
  - `scripts/check-v2-contract.sh`
  - `scripts/run-v2-preflight.sh`
    - includes deploy template validation gate
  - `scripts/check-v2-readiness.py`
  - `scripts/check-v2-locks.py`
  - `scripts/evaluate-v2-cutover.py`
  - `scripts/render-v2-cutover-message.py`
  - `scripts/summarize-v2-contract.sh`
- CI integration:
  - contract/readiness/locks checks
  - cutover evaluation + message rendering
  - artifacts uploaded from `.artifacts/*`

## Quality Gate Snapshot

- Unit/integration tests in this repository:
  - `pytest -q tests`
  - current result: `268 passed, 3 skipped`
- Local contract smoke:
  - `./scripts/check-v2-contract.sh`
  - current result: passed

## Remaining Work (Operational)

1. Staging cutover rehearsal (must-pass)
   - Use `docs/env/v2-cutover-staging.env.example`
   - Capture artifacts:
     - `.artifacts/v2_contract_diff.json`
     - `.artifacts/v2_readiness.json`
     - `.artifacts/v2_locks.json`
     - `.artifacts/v2_cutover_eval.json`
   - Acceptance:
     - `decision=GO` in cutover evaluation
     - no stale locks remain after rehearsal cleanup

2. Production lock-operation procedure finalization
   - Finalize authority boundary for `POST /api/v2/system/locks/release`
   - Define audit log retention for lock-release operations
   - Acceptance:
     - reviewed and approved in runbook

3. Release/cutover execution pack
   - Prepare one-page rollback checklist and command set
   - Pre-assign operators for:
     - API health watch
     - lock queue watch
     - rollback executor
   - Acceptance:
     - dry-run complete with timestamped log

## Remaining Work (Code/Repo Hygiene)

1. Separate unrelated local edits from v2 track
   - Current mixed local changes include:
     - `requirements.txt`
     - `tests/test_auth_basic.py`
     - `tests/test_docker.py`
   - Use `scripts/report-local-diff.sh` before each commit to keep PR scope isolated.

2. CI workflow de-duplication
   - Shared v2 contract/readiness/cutover steps are duplicated in:
     - `.github/workflows/ci.yml`
     - `.github/workflows/integration.yml`
   - Extract common logic into one script entrypoint and keep workflow files thin.

3. Lint policy cleanup
   - Current test modules use selective pylint disables for CI stability.
   - Replace suppressions with structural fixes where low-cost, then tighten `.pylintrc`.

## 日本語訳

# NW-Diff v2 実装ステータス

最終更新: 2026-02-28

## 完了済み

- `src/nw_diff_v2` 配下に v2 API スキャフォールドを実装（task/capture/compare/exports/hosts/logs/system エンドポイント）
- v2 の最小 UI ページ:
  - `/v2`
  - `/v2/hosts/{hostname}`
  - `/v2/logs`
- ホスト単位ロックポリシー:
  - 同一ホストへの同時 capture は拒否
  - 異なるホストの並列 capture は許可
- ロック操作:
  - `GET /api/v2/system/locks`
  - `POST /api/v2/system/locks/cleanup`
  - `POST /api/v2/system/locks/release`
- 起動時リカバリー:
  - 孤立した `running` タスクを `failed` に復旧
  - API/worker 起動時に stale lock をクリーンアップ
- セキュリティ/ランタイムポリシー:
  - 開発系環境以外では `NW_DIFF_API_TOKEN` 必須
  - `hosts.csv` の安全文字、IP/port、長さ上限を検証
- contract/readiness/cutover ツール:
  - `scripts/generate-v2-contract.py`
  - `scripts/diff-v2-contract.py`
  - `scripts/check-v2-contract.sh`
  - `scripts/run-v2-preflight.sh`
    - deploy template validation gate を含む
  - `scripts/check-v2-readiness.py`
  - `scripts/check-v2-locks.py`
  - `scripts/evaluate-v2-cutover.py`
  - `scripts/render-v2-cutover-message.py`
  - `scripts/summarize-v2-contract.sh`
- CI 統合:
  - contract/readiness/locks チェック
  - cutover 評価 + メッセージ生成
  - `.artifacts/*` からアーティファクトをアップロード

## 品質ゲートスナップショット

- このリポジトリのユニット/統合テスト:
  - `pytest -q tests`
  - 現在結果: `268 passed, 3 skipped`
- ローカル contract スモーク:
  - `./scripts/check-v2-contract.sh`
  - 現在結果: passed

## 残作業（運用）

1. Staging 切替リハーサル（必須合格）
   - `docs/env/v2-cutover-staging.env.example` を使用
   - アーティファクトを収集:
     - `.artifacts/v2_contract_diff.json`
     - `.artifacts/v2_readiness.json`
     - `.artifacts/v2_locks.json`
     - `.artifacts/v2_cutover_eval.json`
   - 受け入れ基準:
     - cutover 評価で `decision=GO`
     - リハーサル cleanup 後に stale lock が残らない

2. 本番ロック操作手順の最終化
   - `POST /api/v2/system/locks/release` の権限境界を最終決定
   - lock-release 操作の監査ログ保持方針を定義
   - 受け入れ基準:
     - runbook でレビュー/承認済み

3. リリース/切替実行パック
   - 1ページのロールバックチェックリストとコマンドセットを準備
   - 次の担当を事前割当:
     - API ヘルス監視
     - lock キュー監視
     - ロールバック実行
   - 受け入れ基準:
     - タイムスタンプ付きログでドライラン完了

## 残作業（コード/リポジトリ衛生）

1. v2 トラックと無関係なローカル編集を分離
   - 現在の混在ローカル変更:
     - `requirements.txt`
     - `tests/test_auth_basic.py`
     - `tests/test_docker.py`
   - 各コミット前に `scripts/report-local-diff.sh` を使い PR スコープを分離。

2. CI ワークフロー重複排除
   - 共有 v2 contract/readiness/cutover 手順が次に重複:
     - `.github/workflows/ci.yml`
     - `.github/workflows/integration.yml`
   - 共通ロジックを 1 つのスクリプト入口へ抽出し、workflow ファイルを薄く保つ。

3. Lint ポリシー整理
   - 現在のテストモジュールは CI 安定性のため選択的な pylint disable を利用。
   - 低コストで置換可能な suppressions を構造的修正に置き換え、`.pylintrc` を引き締める。
