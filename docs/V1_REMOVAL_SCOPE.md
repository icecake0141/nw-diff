# V1 Removal Scope

Last updated: 2026-03-03

This document defines the exact scope for full v1 removal (`src/nw_diff`) and the expected PR slicing.

## Goal

Move repository runtime and maintenance scope to v2-only (`src/nw_diff_v2`) and remove legacy Flask v1 implementation safely.

## In Scope (to remove)

### Runtime and package

- `run_app.py`
- `src/nw_diff/` package:
  - `app.py`
  - `auth.py`
  - `devices.py`
  - `diff.py`
  - `logging_config.py`
  - `security.py`
  - `storage.py`
  - `__init__.py`

### Tests and CI

- Remove v1-focused tests:
  - `tests/test_app.py`
  - v1 import test in `tests/test_installation.py`
  - any tests targeting `/api/logs` (v1 route) via `nw_diff.app`
- Remove `legacy_v1` CI execution:
  - `pytest -m "legacy_v1"` in `.github/workflows/ci.yml`
- Remove `legacy_v1` marker registration in `pytest.ini` once no test uses it.

### Docs

- Remove v1 runtime guidance and "legacy v1 entrypoint" statements from:
  - `README.md`
  - `docs/README_ja.md`
  - `docs/SPEC.md`
- Archive or rewrite migration wording in `docs/V2_MIGRATION.md` as needed after v1 deletion.

## In Scope (to migrate before deletion)

The following v2 modules currently import `nw_diff.diff` and must be switched to v2-native implementation before deleting `src/nw_diff`:

- `src/nw_diff_v2/api/compare.py`
- `src/nw_diff_v2/api/hosts.py`
- `src/nw_diff_v2/api/exports.py`

## Compatibility Stubs

- Keep temporary compatibility stubs: **none**.
- v1 removal is treated as a breaking change; callers must use v2 endpoints and startup commands.

## Out of Scope

- Changing v2 API contract paths under `/api/v2/*`.
- New feature work unrelated to v1 deletion.
- Operational cutover rehearsals and staffing tasks in `TODO.md`.

## Safe PR Slicing

1. PR-A: Migrate v2 code imports off `nw_diff.diff`.
2. PR-B: Remove/replace tests that import `nw_diff.*` (except historical docs artifacts).
3. PR-C: Remove `legacy_v1` CI run and marker.
4. PR-D: Delete `run_app.py` and `src/nw_diff/`.
5. PR-E: Final docs cleanup and breaking-change release notes.
