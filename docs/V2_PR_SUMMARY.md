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
