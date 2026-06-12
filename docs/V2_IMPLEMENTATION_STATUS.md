# NW-Diff v2 Implementation Status

Last updated: 2026-06-13

## Completed

- v2 API scaffold under `src/nw_diff_v2` with task/capture/compare/exports/hosts/logs/system endpoints
- v2 minimal UI pages:
  - `/v2`
  - `/v2/hosts/{hostname}`
  - `/v2/logs`
- v2 UI maintainability updates:
  - `/v2` page CSS and JavaScript are served from `src/nw_diff_v2/static/`
  - `/v2/static` is mounted by the FastAPI app
  - control panel section jumps are available for Hosts, Tasks, Console, Export, Compare, and Diagnostics
- v2 focused test suites:
  - `tests/test_v2_capture_api.py`
  - `tests/test_v2_tasks.py`
  - `tests/test_v2_system.py`
  - `tests/test_v2_ui.py`
  - `tests/test_v2_end_to_end.py`
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
  - current result: `147 passed`
- Static analysis and lint:
  - `mypy src/nw_diff_v2 tests/test_v2_core_services.py tests/test_v2_worker.py tests/test_v2_export_compare.py tests/test_v2_hosts_diff.py tests/test_v2_logs.py tests/test_v2_system.py tests/test_v2_tasks.py tests/test_v2_capture_api.py tests/test_v2_ui.py tests/test_v2_end_to_end.py tests/v2_helpers.py`
  - current result: passed
  - `pylint src/nw_diff_v2 tests/test_v2_core_services.py tests/test_v2_worker.py tests/test_v2_export_compare.py tests/test_v2_hosts_diff.py tests/test_v2_logs.py tests/test_v2_system.py tests/test_v2_tasks.py tests/test_v2_capture_api.py tests/test_v2_ui.py tests/test_v2_end_to_end.py tests/v2_helpers.py`
  - current result: `10.00/10`
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

No high-priority code/repository hygiene work is currently open.

- The working tree is clean and `main` is in sync with `origin/main` as of this update.
- The v2 scaffold test file has been replaced by focused test suites.
- CI and integration workflows both call `scripts/run-v2-ci-contract-suite.sh` for the shared v2 contract/post-check path.
- Low-value pylint suppressions have been reduced where practical; remaining suppressions are scoped to test ergonomics.

## 日本語訳

# NW-Diff v2 実装ステータス

最終更新: 2026-06-13

## 完了済み

- `src/nw_diff_v2` 配下に v2 API スキャフォールドを実装（task/capture/compare/exports/hosts/logs/system エンドポイント）
- v2 の最小 UI ページ:
  - `/v2`
  - `/v2/hosts/{hostname}`
  - `/v2/logs`
- v2 UI の保守性改善:
  - `/v2` ページの CSS/JavaScript は `src/nw_diff_v2/static/` から配信
  - FastAPI app が `/v2/static` を mount
  - Control Panel に Hosts / Tasks / Console / Export / Compare / Diagnostics のセクションジャンプを追加
- v2 の責務別テストスイート:
  - `tests/test_v2_capture_api.py`
  - `tests/test_v2_tasks.py`
  - `tests/test_v2_system.py`
  - `tests/test_v2_ui.py`
  - `tests/test_v2_end_to_end.py`
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
  - 現在結果: `147 passed`
- 静的解析と lint:
  - `mypy src/nw_diff_v2 tests/test_v2_core_services.py tests/test_v2_worker.py tests/test_v2_export_compare.py tests/test_v2_hosts_diff.py tests/test_v2_logs.py tests/test_v2_system.py tests/test_v2_tasks.py tests/test_v2_capture_api.py tests/test_v2_ui.py tests/test_v2_end_to_end.py tests/v2_helpers.py`
  - 現在結果: passed
  - `pylint src/nw_diff_v2 tests/test_v2_core_services.py tests/test_v2_worker.py tests/test_v2_export_compare.py tests/test_v2_hosts_diff.py tests/test_v2_logs.py tests/test_v2_system.py tests/test_v2_tasks.py tests/test_v2_capture_api.py tests/test_v2_ui.py tests/test_v2_end_to_end.py tests/v2_helpers.py`
  - 現在結果: `10.00/10`
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

現時点で優先度の高いコード/リポジトリ衛生タスクはありません。

- 作業ツリーは clean で、この更新時点の `main` は `origin/main` と同期済み。
- v2 scaffold テストファイルは責務別テストスイートへ置換済み。
- CI / integration workflow は共通の v2 contract/post-check 経路として `scripts/run-v2-ci-contract-suite.sh` を利用。
- 低価値な pylint suppressions は実用的な範囲で削減済み。残る suppressions はテスト記述上の局所的なもの。
