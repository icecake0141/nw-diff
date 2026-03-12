<!--
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->

# NW-Diff プロジェクト（日本語ガイド）

[![CI](https://github.com/icecake0141/nw-diff/workflows/CI/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/ci.yml)
[![Integration Tests](https://github.com/icecake0141/nw-diff/workflows/Integration%20Tests/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/integration.yml)

NW-Diff はネットワーク機器向けのキャプチャ/差分比較ツールです。

- ランタイム: v2 `src/nw_diff_v2`（FastAPI）

現在のコンテナ標準起動は v2 のみです。

## インストール

### 前提条件

- Python 3.11+
- `pip`
- Git
- 対象機器への SSH 到達性

### クイックスタート（ローカル v2）

1. リポジトリを取得:
```bash
git clone https://github.com/icecake0141/nw-diff.git
cd nw-diff
```

2. 仮想環境を作成・有効化:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. 依存関係をインストール:
```bash
pip install -r requirements.txt -r requirements-v2.txt
```

4. インベントリを準備:
```bash
cp hosts.csv.sample hosts.csv
```

5. 必須環境変数を設定:
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
# `NW_DIFF_ENV` が dev/development/local/test 以外のときのみ必須
# export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

6. v2 API/UI を起動:
```bash
./scripts/start-v2.sh
```
- 起動前に必須環境変数の状態を表示します。
- センシティブな値はマスク表示されます。
- 直接 `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` を実行する方法も後方互換として利用できます。

7. 動作確認:
- <http://127.0.0.1:5000/v2>
- <http://127.0.0.1:5000/api/v2/system/health>

## ドキュメント一覧

- 言語運用方針:
  - 原則として各ドキュメントは 1 ファイル内で英語 + 日本語訳を併記します。
  - トップガイドは `README.md`（英語中心）と `README_ja.md`（日本語中心）に分けて管理します。
- [トップ README（英語）](README.md)
- [仕様（SPEC）](docs/SPEC.md)
- [テスト手順](docs/TESTING.md)
- [V2 移行ガイド](docs/V2_MIGRATION.md)
- [V2 Runbook](docs/V2_RUNBOOK.md)
- [V2 切替チェックリスト](docs/V2_CUTOVER_CHECKLIST.md)
- [V2 実装ステータス](docs/V2_IMPLEMENTATION_STATUS.md)
- [V2 PR サマリ](docs/V2_PR_SUMMARY.md)
- [V2 コミット分割計画](docs/V2_COMMIT_SPLIT_PLAN.md)
- [V2 契約スナップショット](docs/contract/v2.json)
- [起動ガイド概要](docs/startup/STARTUP_OVERVIEW.md)
- [環境別起動手順](docs/startup/STARTUP_ENVIRONMENTS.md)
- [クイックテスト起動](docs/startup/STARTUP_QUICK_TEST.md)
- [Docker/Podman 起動ガイド](docs/startup/STARTUP_DOCKER.md)
- [起動トラブルシューティング](docs/startup/STARTUP_TROUBLESHOOTING.md)
- [デプロイガイド](docs/deploy/README.md)
- [nginx テンプレート（v2）](docs/deploy/nginx-v2.conf.example)
- [systemd API サービステンプレート](docs/deploy/nw-diff-v2-api.service.example)
- [systemd Worker サービステンプレート](docs/deploy/nw-diff-v2-worker.service.example)

## 補足

- `docker-compose.yml` は v2 を標準起動します。
- `docker-compose.yml` は Docker Compose と Podman Compose 互換ランタイムで利用できます（best-effort）。
- 破壊的変更: 旧 v1 パスは削除済みです。
- `run_app.py` や `src/nw_diff` を使っていた場合は、`./scripts/start-v2.sh` または `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src` に切り替えてください。
- 移行メモは `docs/V2_MIGRATION.md` を参照してください。
