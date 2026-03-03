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

- Spec: `docs/SPEC.md`
- Testing: `docs/TESTING.md`
- Startup guides: `docs/startup/STARTUP_OVERVIEW.md`
- Deploy guides/templates: `docs/deploy/README.md`
- V2 migration: `docs/V2_MIGRATION.md`
- V2 runbook: `docs/V2_RUNBOOK.md`
- Japanese docs: `docs/README_ja.md`

## Notes

- `docker-compose.yml` runs v2 by default.
- Legacy v1 instructions are intentionally not duplicated in this top-level README.
