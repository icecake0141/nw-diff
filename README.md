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

# NW-Diff Project

[![CI](https://github.com/icecake0141/nw-diff/workflows/CI/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/ci.yml)
[![Integration Tests](https://github.com/icecake0141/nw-diff/workflows/Integration%20Tests/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/integration.yml)

NW-Diff is a network capture and diff tool for network devices.

- Runtime: v2 `src/nw_diff_v2` (FastAPI)

The default container runtime is v2 only.

## Installation

### Prerequisites

- Python 3.11+
- `pip`
- Git
- SSH reachability to target devices

### Quick Start (Local v2)

1. Clone repository:
```bash
git clone https://github.com/icecake0141/nw-diff.git
cd nw-diff
```

2. Create and activate a virtual environment (`venv`):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt -r requirements-v2.txt
```

4. Prepare inventory:
```bash
cp hosts.csv.sample hosts.csv
```

5. (Optional) Override per-model command profiles:
```bash
cp command_profiles/device_commands.override.yaml.sample \
  command_profiles/device_commands.override.yaml
```
- Edit `command_profiles/device_commands.override.yaml` to fully replace defaults.
- Invalid YAML or schema causes startup failure (fail closed).
- Remove `command_profiles/device_commands.override.yaml` to return to defaults.

6. Set required environment variables:
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
# Optional: custom override path
# export COMMAND_PROFILES_OVERRIDE_YAML=command_profiles/device_commands.override.yaml
```

7. Start v2 API/UI:
```bash
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

8. Open:
- <http://127.0.0.1:5000/v2>
- <http://127.0.0.1:5000/api/v2/system/health>

## Documentation

- Language policy:
  - Most docs are bilingual in a single file (English + Japanese section).
  - Top guides can be split as `README.md` (EN-focused) and `README_ja.md` (JA-focused).
- [Main Japanese guide](README_ja.md)
- [Spec](docs/SPEC.md)
- [Testing](docs/TESTING.md)
- [V2 migration](docs/V2_MIGRATION.md)
- [V2 runbook](docs/V2_RUNBOOK.md)
- [V2 cutover checklist](docs/V2_CUTOVER_CHECKLIST.md)
- [V2 implementation status](docs/V2_IMPLEMENTATION_STATUS.md)
- [V2 PR summary](docs/V2_PR_SUMMARY.md)
- [V2 commit split plan](docs/V2_COMMIT_SPLIT_PLAN.md)
- [V2 contract snapshot](docs/contract/v2.json)
- [Startup overview](docs/startup/STARTUP_OVERVIEW.md)
- [Startup by environment](docs/startup/STARTUP_ENVIRONMENTS.md)
- [Startup quick test](docs/startup/STARTUP_QUICK_TEST.md)
- [Startup docker/podman guide](docs/startup/STARTUP_DOCKER.md)
- [Startup troubleshooting](docs/startup/STARTUP_TROUBLESHOOTING.md)
- [Deploy guide](docs/deploy/README.md)
- [Deploy nginx (v2)](docs/deploy/nginx-v2.conf.example)
- [Deploy systemd API service](docs/deploy/nw-diff-v2-api.service.example)
- [Deploy systemd worker service](docs/deploy/nw-diff-v2-worker.service.example)

## Integration Testing

- Run Docker-based integration checks with `./scripts/test-integration.sh`.

## 日本語概要

NW-Diff はネットワーク機器向けのキャプチャ/差分比較ツールです。

- ランタイム: v2 `src/nw_diff_v2`（FastAPI）

現在のコンテナ標準起動は v2 のみです。

### インストール（ローカル v2 最短手順）

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

5. （任意）モデル別コマンド定義を上書き:
```bash
cp command_profiles/device_commands.override.yaml.sample \
  command_profiles/device_commands.override.yaml
```
- `command_profiles/device_commands.override.yaml` を編集するとデフォルト定義を全置換します。
- YAML/スキーマが不正な場合は起動時にエラーで停止します（fail closed）。
- デフォルトに戻すには `command_profiles/device_commands.override.yaml` を削除します。

6. 必須環境変数を設定:
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
# 任意: 上書きファイルのパスを変更
# export COMMAND_PROFILES_OVERRIDE_YAML=command_profiles/device_commands.override.yaml
```

7. v2 API/UI を起動:
```bash
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

8. 動作確認:
- <http://127.0.0.1:5000/v2>
- <http://127.0.0.1:5000/api/v2/system/health>

## Notes

- `docker-compose.yml` runs v2 by default.
- `docker-compose.yml` can be used with Docker Compose and Podman Compose compatible runtimes (best-effort).
- Breaking change: legacy v1 paths were removed.
- If you used `run_app.py` or `src/nw_diff`, switch to `uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src`.
- See migration notes in `docs/V2_MIGRATION.md`.
