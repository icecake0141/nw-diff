"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 capture API tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position,wrong-import-order

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureTaskStatus
from nw_diff_v2.domain.services import capture_service
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.main import app
from v2_helpers import configure_v2_test_env, write_hosts_csv

CAPTURE_QUEUE_LAUNCH = (
    "nw_diff_v2.domain.services.capture_queue_service.launch_capture_task"
)
CAPTURE_QUEUE_LOCK = "nw_diff_v2.domain.services.capture_queue_service.try_lock_hosts"


@pytest.fixture(autouse=True)
def reset_command_profiles(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing-command-profiles.yaml"
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(missing))
    capture_service.validate_command_profile_config()


def _patch_completed_capture(monkeypatch) -> None:
    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        del base
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(CAPTURE_QUEUE_LAUNCH, _fake_launch_capture_task)


def test_v2_capture_api_creates_task_and_status_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    _patch_completed_capture(monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": ["router1"]},
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]

        status_response = client.get(f"/api/v2/tasks/{task_id}")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert payload["task_id"] == task_id
        assert payload["status"] == "completed"


def test_v2_batch_skip_locked_policy(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    monkeypatch.setattr(settings, "batch_conflict_policy", "skip_locked")
    _patch_completed_capture(monkeypatch)

    acquired, _ = try_lock_hosts({"router1"})
    assert acquired is True
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v2/captures",
                json={"mode": "batch", "base": "origin", "hosts": []},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["conflicts"] == ["router1"]

            task_id = payload["task_id"]
            status_response = client.get(f"/api/v2/tasks/{task_id}")
            assert status_response.status_code == 200
            status_payload = status_response.json()
            assert status_payload["hosts"] == ["router2"]
    finally:
        release_hosts({"router1"})


def test_v2_batch_skip_locked_reports_retry_conflicts(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    monkeypatch.setattr(settings, "batch_conflict_policy", "skip_locked")

    call_count = {"value": 0}

    def _fake_try_lock_hosts(hosts):  # noqa: ANN001
        del hosts
        call_count["value"] += 1
        if call_count["value"] == 1:
            return False, {"router1"}
        return False, {"router2"}

    monkeypatch.setattr(CAPTURE_QUEUE_LOCK, _fake_try_lock_hosts)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/captures",
            json={"mode": "batch", "base": "origin", "hosts": []},
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Capture already running: router2"


def test_v2_capture_allows_parallel_on_different_host(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    _patch_completed_capture(monkeypatch)

    acquired, _ = try_lock_hosts({"router1"})
    assert acquired is True
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v2/captures",
                json={"mode": "single", "base": "origin", "hosts": ["router2"]},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["conflicts"] == []
            task_id = payload["task_id"]

            status_response = client.get(f"/api/v2/tasks/{task_id}")
            assert status_response.status_code == 200
            status_payload = status_response.json()
            assert status_payload["hosts"] == ["router2"]
    finally:
        release_hosts({"router1"})


def test_v2_single_mode_requires_exactly_one_host(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        no_host = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": []},
        )
        assert no_host.status_code == 400
        assert "exactly one host" in no_host.json()["detail"]

        many_hosts = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": ["router1", "router2"]},
        )
        assert many_hosts.status_code == 400
        assert "exactly one host" in many_hosts.json()["detail"]


def test_v2_batch_mode_can_target_subset(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
            "router3,10.0.0.3,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    captured_hosts: list[list[str]] = []

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        del base
        captured_hosts.append(sorted([h["host"] for h in hosts]))
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(CAPTURE_QUEUE_LAUNCH, _fake_launch_capture_task)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/captures",
            json={"mode": "batch", "base": "origin", "hosts": ["router1", "router3"]},
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]

        status_response = client.get(f"/api/v2/tasks/{task_id}")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert sorted(payload["hosts"]) == ["router1", "router3"]

    assert captured_hosts == [["router1", "router3"]]
