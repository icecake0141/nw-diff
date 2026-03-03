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

- v1（旧実装）: `src/nw_diff`（Flask）
- v2（標準）: `src/nw_diff_v2`（FastAPI）

現在のコンテナ標準起動は v2 です。

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
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

6. v2 API/UI を起動:
```bash
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

7. 動作確認:
- <http://127.0.0.1:5000/v2>
- <http://127.0.0.1:5000/api/v2/system/health>

## ドキュメント一覧

- 言語運用方針:
  - 原則として各ドキュメントは 1 ファイル内で英語 + 日本語訳を併記します。
  - トップガイドは `README.md`（英語中心）と `docs/README_ja.md`（日本語中心）に分けて管理します。
- [トップ README（英語）](../README.md)
- [仕様（SPEC）](SPEC.md)
- [テスト手順](TESTING.md)
- [V2 移行ガイド](V2_MIGRATION.md)
- [V2 Runbook](V2_RUNBOOK.md)
- [V2 切替チェックリスト](V2_CUTOVER_CHECKLIST.md)
- [V2 実装ステータス](V2_IMPLEMENTATION_STATUS.md)
- [V2 PR サマリ](V2_PR_SUMMARY.md)
- [V2 コミット分割計画](V2_COMMIT_SPLIT_PLAN.md)
- [V2 契約スナップショット](contract/v2.json)
- [起動ガイド概要](startup/STARTUP_OVERVIEW.md)
- [環境別起動手順](startup/STARTUP_ENVIRONMENTS.md)
- [クイックテスト起動](startup/STARTUP_QUICK_TEST.md)
- [Docker 起動ガイド](startup/STARTUP_DOCKER.md)
- [起動トラブルシューティング](startup/STARTUP_TROUBLESHOOTING.md)
- [デプロイガイド](deploy/README.md)
- [nginx テンプレート（v2）](deploy/nginx-v2.conf.example)
- [nginx テンプレート（v1->v2 cutover）](deploy/nginx-v1-v2-cutover.conf.example)
- [systemd API サービステンプレート](deploy/nw-diff-v2-api.service.example)
- [systemd Worker サービステンプレート](deploy/nw-diff-v2-worker.service.example)

## 補足

- `docker-compose.yml` は v2 を標準起動します。
- 旧 v1 の詳細説明はトップ README には重複掲載しません。
