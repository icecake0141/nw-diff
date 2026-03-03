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

- v1 (legacy): `src/nw_diff` (Flask)
- v2 (default): `src/nw_diff_v2` (FastAPI)

The default container runtime is v2.

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

5. Set required environment variables:
```bash
export DEVICE_PASSWORD=your_device_password
export NW_DIFF_ENV=development
export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

6. Start v2 API/UI:
```bash
uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
```

7. Open:
- <http://127.0.0.1:5000/v2>
- <http://127.0.0.1:5000/api/v2/system/health>

## Documentation

- [Main Japanese guide](docs/README_ja.md)
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
- [Startup docker guide](docs/startup/STARTUP_DOCKER.md)
- [Startup troubleshooting](docs/startup/STARTUP_TROUBLESHOOTING.md)
- [Deploy guide](docs/deploy/README.md)
- [Deploy nginx (v2)](docs/deploy/nginx-v2.conf.example)
- [Deploy nginx (v1->v2 cutover)](docs/deploy/nginx-v1-v2-cutover.conf.example)
- [Deploy systemd API service](docs/deploy/nw-diff-v2-api.service.example)
- [Deploy systemd worker service](docs/deploy/nw-diff-v2-worker.service.example)

## Integration Testing

- Run Docker-based integration checks with `./scripts/test-integration.sh`.

## 日本語概要

NW-Diff はネットワーク機器向けのキャプチャ/差分比較ツールです。

- v1（旧実装）: `src/nw_diff`（Flask）
- v2（標準）: `src/nw_diff_v2`（FastAPI）

現在のコンテナ標準起動は v2 です。

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

## Notes

- `docker-compose.yml` runs v2 by default.
- Legacy v1 instructions are intentionally not duplicated in this top-level README.
- `run_app.py` is kept as a legacy v1 (Flask) entrypoint only.
