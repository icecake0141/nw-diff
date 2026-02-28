# V2 Reimplementation PR Summary

## Branch

- `codex/reimpl-scaffold`

## Split Commits

1. `0bd82ec` feat(v2-core): add FastAPI v2 scaffold and task/capture/compare/export APIs
2. `ce5bc8e` feat(v2-ops): add contract/readiness/locks/cutover tooling
3. `ba19b25` feat(v2-deploy): add deploy templates and validation
4. `a8b34f7` ci(v2): integrate v2 contract/readiness/locks/cutover checks
5. `12f9dc9` docs(v2): add migration/runbook/checklist/status and contract snapshot
6. `08963c3` chore: ignore generated v2 artifacts

## Highlights

- Introduced `src/nw_diff_v2` FastAPI scaffold with API/UI/worker/task persistence.
- Enforced host-level concurrency policy:
  - same host: blocked
  - different hosts: parallel allowed
- Added lock operations and observability:
  - list / cleanup / release
  - lock owner hints in system locks endpoint
- Added startup recovery:
  - stale lock cleanup
  - orphan running task recovery
- Added operational tooling:
  - contract/readiness/locks checks
  - cutover evaluate/render tools
  - aggregated preflight runner
- Wired CI/integration workflows for v2 validation and artifact publication.
- Added migration/runbook/checklist/status documentation.

## Verification

- Test suite: `268 passed, 3 skipped`
- Local preflight: `scripts/run-v2-preflight.sh` succeeded with `GO`

## Remaining Non-v2 Working Tree Changes

The following files remain modified and are not included in the v2 split commits:

- `requirements-dev.txt`
- `requirements.txt`
- `src/nw_diff/app.py`
- `tests/test_auth_basic.py`
- `tests/test_docker.py`
- `tests/test_installation.py`

## 日本語訳

# V2 再実装 PR サマリー

## ブランチ

- `codex/reimpl-scaffold`

## 分割コミット

1. `0bd82ec` feat(v2-core): FastAPI v2 スキャフォールドと task/capture/compare/export API を追加
2. `ce5bc8e` feat(v2-ops): contract/readiness/locks/cutover ツールを追加
3. `ba19b25` feat(v2-deploy): デプロイテンプレートと検証を追加
4. `a8b34f7` ci(v2): v2 contract/readiness/locks/cutover チェックを CI に統合
5. `12f9dc9` docs(v2): migration/runbook/checklist/status と contract snapshot を追加
6. `08963c3` chore: 生成された v2 アーティファクトを無視

## ハイライト

- API/UI/worker/task 永続化を備える `src/nw_diff_v2` FastAPI スキャフォールドを導入。
- ホスト単位の同時実行ポリシーを適用:
  - 同一ホスト: ブロック
  - 異なるホスト: 並列許可
- ロック操作と可観測性を追加:
  - list / cleanup / release
  - system locks エンドポイントに lock owner ヒント
- 起動時リカバリーを追加:
  - stale lock cleanup
  - 孤立 running task recovery
- 運用ツールを追加:
  - contract/readiness/locks チェック
  - cutover evaluate/render ツール
  - 集約 preflight ランナー
- v2 検証とアーティファクト公開のため CI/integration workflow を接続。
- migration/runbook/checklist/status ドキュメントを追加。

## 検証

- テストスイート: `268 passed, 3 skipped`
- ローカル preflight: `scripts/run-v2-preflight.sh` が `GO` で成功

## v2 以外の残存ワークツリー変更

以下ファイルは変更済みだが、v2 分割コミットには含まれていません:

- `requirements-dev.txt`
- `requirements.txt`
- `src/nw_diff/app.py`
- `tests/test_auth_basic.py`
- `tests/test_docker.py`
- `tests/test_installation.py`
