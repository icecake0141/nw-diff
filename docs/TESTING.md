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
