# Testing Guide

## Local Test Commands

Run unit/integration tests:

```bash
pytest -q tests
```

Run a focused documentation/install check:

```bash
pytest -q tests/test_installation.py
```

## v2 Contract and Readiness Checks

Contract smoke:

```bash
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/check-v2-contract.sh
```

Preflight bundle:

```bash
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/run-v2-preflight.sh
```

## Docker Integration

Run stack and integration script manually:

```bash
docker compose up -d --build
./scripts/test-integration.sh
```

Cleanup:

```bash
docker compose down -v
```

## CI Workflows

- CI: `.github/workflows/ci.yml`
- Integration: `.github/workflows/integration.yml`

These workflows validate tests, docker integration, and v2 contract/readiness/cutover checks.

## 日本語訳

## ローカルテストコマンド

ユニット/統合テスト:

```bash
pytest -q tests
```

インストール/ドキュメント系の確認:

```bash
pytest -q tests/test_installation.py
```

## v2 契約・Readiness チェック

contract スモーク:

```bash
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/check-v2-contract.sh
```

preflight 一式:

```bash
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/run-v2-preflight.sh
```

## Docker 統合テスト

手動でスタック起動＋統合スクリプト実行:

```bash
docker compose up -d --build
./scripts/test-integration.sh
```

停止/クリーンアップ:

```bash
docker compose down -v
```

## CI ワークフロー

- CI: `.github/workflows/ci.yml`
- Integration: `.github/workflows/integration.yml`

これらのワークフローで、テスト・docker統合・v2 contract/readiness/cutover チェックを自動検証します。
