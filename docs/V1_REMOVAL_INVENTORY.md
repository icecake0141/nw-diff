# V1 Removal Inventory

Last updated: 2026-03-03

This document inventories repository references that depend on legacy v1 (`src/nw_diff`) so v1 deletion can be executed in safe, incremental PRs.

## 1) Runtime/Entry Points

- `run_app.py`
  - Legacy Flask startup wrapper (explicitly marked legacy).
- `src/nw_diff/app.py`
  - Flask app module and `/api/logs` route.

## 2) v1 Package/Modules

- `src/nw_diff/`
  - `app.py`
  - `auth.py`
  - `devices.py`
  - `diff.py`
  - `logging_config.py`
  - `security.py`
  - `storage.py`
  - `__init__.py`

## 3) v2 Runtime Code Still Importing v1 Utilities

These must be migrated before deleting `src/nw_diff`.

- `src/nw_diff_v2/api/compare.py`
  - imports `nw_diff.diff`
- `src/nw_diff_v2/api/hosts.py`
  - imports `nw_diff.diff`
- `src/nw_diff_v2/api/exports.py`
  - imports `nw_diff.diff`

## 4) Tests (legacy v1 scope)

- `tests/test_app.py`
  - marked `legacy_v1`; imports and validates Flask app behavior.
- `tests/test_installation.py`
  - `test_legacy_v1_app_can_import` marked `legacy_v1`.
- `tests/test_auth_basic.py`
  - imports `nw_diff.app` and exercises `/api/logs`.
- `tests/test_diff_context.py`
  - imports `nw_diff.diff`.

## 5) CI/Workflow References

- `.github/workflows/ci.yml`
  - includes `pytest -m "legacy_v1"` test run.

## 6) Documentation References

- `README.md`
  - states v1 legacy location and `run_app.py` legacy entrypoint.
- `docs/README_ja.md`
  - v1 legacy mention.
- `docs/SPEC.md`
  - legacy runtime section (`src/nw_diff`).
- `docs/V2_MIGRATION.md`
  - migration from v1 Flask to v2 FastAPI.
- `docs/V2_PR_SUMMARY.md`
  - historical references to `src/nw_diff/app.py`.

## 7) Suggested Deletion Order

1. Replace v2 imports of `nw_diff.diff` with v2-native module(s).
2. Remove/replace tests importing `nw_diff.*` outside explicitly archived historical test packs.
3. Remove `legacy_v1` CI stage.
4. Remove `run_app.py`.
5. Remove `src/nw_diff/` package.
6. Clean up docs to v2-only runtime language.
