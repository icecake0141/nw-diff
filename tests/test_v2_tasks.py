"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 task API tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position,wrong-import-order

from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from nw_diff_v2.domain.models import CaptureTaskStatus
from nw_diff_v2.domain.services.lock_service import release_hosts
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.main import app
from v2_helpers import configure_v2_test_env, write_hosts_csv

CAPTURE_QUEUE_LAUNCH = (
    "nw_diff_v2.domain.services.capture_queue_service.launch_capture_task"
)


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


def _patch_queued_capture(monkeypatch) -> None:
    def _noop_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        del task_id, base, hosts, reserved_hosts

    monkeypatch.setattr(CAPTURE_QUEUE_LAUNCH, _noop_launch_capture_task)


def test_v2_task_list_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    _patch_completed_capture(monkeypatch)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": ["router1"]},
        )
        assert create_response.status_code == 200

        list_response = client.get("/api/v2/tasks?limit=5")
        assert list_response.status_code == 200
        payload = list_response.json()
        assert isinstance(payload, list)
        assert len(payload) >= 1
        assert payload[0]["task_id"] == create_response.json()["task_id"]


def test_v2_task_cancel_endpoint_sets_flag(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    _patch_queued_capture(monkeypatch)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": ["router1"]},
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["task_id"]

        cancel_response = client.post(f"/api/v2/tasks/{task_id}/cancel")
        assert cancel_response.status_code == 200
        payload = cancel_response.json()
        assert payload["task_id"] == task_id
        assert payload["cancel_requested"] is True


def test_v2_task_endpoints_reject_invalid_task_id(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    bad_id = "%3Cbad%3E"
    with TestClient(app) as client:
        status_resp = client.get(f"/api/v2/tasks/{bad_id}")
        cancel_resp = client.post(f"/api/v2/tasks/{bad_id}/cancel")
        retry_resp = client.post(f"/api/v2/tasks/{bad_id}/retry")
        stream_resp = client.get(f"/api/v2/tasks/{bad_id}/stream")
        assert status_resp.status_code == 400
        assert cancel_resp.status_code == 400
        assert retry_resp.status_code == 400
        assert stream_resp.status_code == 400
        assert status_resp.json()["detail"] == "Invalid task_id"


def test_v2_task_cancel_rejects_completed_task(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    task_repo.create_task(
        task_id="done-task",
        mode="single",
        base="origin",
        hosts=["router1"],
    )
    task_repo.update_task(
        "done-task",
        status=CaptureTaskStatus.COMPLETED,
        started_at=1.0,
        finished_at=2.0,
        result={"success_count": 1, "failure_count": 0},
    )

    with TestClient(app) as client:
        response = client.post("/api/v2/tasks/done-task/cancel")
        assert response.status_code == 409
        assert "already completed" in response.json()["detail"]


def test_v2_task_retry_creates_new_task(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    task_repo.create_task(
        task_id="old-task",
        mode="single",
        base="origin",
        hosts=["router1"],
    )
    task_repo.update_task(
        "old-task",
        status=CaptureTaskStatus.FAILED,
        started_at=1.0,
        finished_at=2.0,
        error="x",
    )
    _patch_queued_capture(monkeypatch)

    with TestClient(app) as client:
        response = client.post("/api/v2/tasks/old-task/retry")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "queued"
        new_task = task_repo.get_task(payload["task_id"])
        assert new_task is not None
        assert new_task["status"] == "queued"
        assert new_task["hosts"] == ["router1"]


def test_v2_task_retry_rejects_queued_task(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    task_repo.create_task(
        task_id="queued-task",
        mode="single",
        base="origin",
        hosts=["router1"],
    )

    with TestClient(app) as client:
        response = client.post("/api/v2/tasks/queued-task/retry")
        assert response.status_code == 409
        assert "still queued" in response.json()["detail"]


def test_v2_task_list_status_filter(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    release_hosts({"router1", "router2"})

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        del base
        status = (
            CaptureTaskStatus.COMPLETED
            if hosts[0]["host"] == "router1"
            else CaptureTaskStatus.FAILED
        )
        task_repo.update_task(
            task_id,
            status=status,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": 1 if status == CaptureTaskStatus.COMPLETED else 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(CAPTURE_QUEUE_LAUNCH, _fake_launch_capture_task)

    try:
        with TestClient(app) as client:
            r1 = client.post(
                "/api/v2/captures",
                json={"mode": "single", "base": "origin", "hosts": ["router1"]},
            )
            assert r1.status_code == 200
            r2 = client.post(
                "/api/v2/captures",
                json={"mode": "single", "base": "origin", "hosts": ["router2"]},
            )
            assert r2.status_code == 200

            completed = client.get("/api/v2/tasks?limit=10&status_filter=completed")
            assert completed.status_code == 200
            completed_payload = completed.json()
            assert len(completed_payload) >= 1
            assert all(item["status"] == "completed" for item in completed_payload)

            failed = client.get("/api/v2/tasks?limit=10&status_filter=failed")
            assert failed.status_code == 200
            failed_payload = failed.json()
            assert len(failed_payload) >= 1
            assert all(item["status"] == "failed" for item in failed_payload)

            host_filtered = client.get("/api/v2/tasks?limit=10&host_contains=router1")
            assert host_filtered.status_code == 200
            host_payload = host_filtered.json()
            assert len(host_payload) >= 1
            assert all("router1" in item["hosts"] for item in host_payload)

            running_filtered = client.get("/api/v2/tasks?limit=10&running_only=true")
            assert running_filtered.status_code == 200
            running_payload = running_filtered.json()
            assert all(item["status"] == "running" for item in running_payload)
    finally:
        release_hosts({"router1", "router2"})


def test_v2_task_list_supports_offset(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
            "router3,10.0.0.3,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    _patch_completed_capture(monkeypatch)

    created_task_ids: list[str] = []
    with TestClient(app) as client:
        for host in ("router1", "router2", "router3"):
            response = client.post(
                "/api/v2/captures",
                json={"mode": "single", "base": "origin", "hosts": [host]},
            )
            assert response.status_code == 200
            created_task_ids.append(response.json()["task_id"])

        page1 = client.get("/api/v2/tasks?limit=1&offset=0")
        page2 = client.get("/api/v2/tasks?limit=1&offset=1")
        assert page1.status_code == 200
        assert page2.status_code == 200
        p1 = page1.json()
        p2 = page2.json()
        assert len(p1) == 1
        assert len(p2) == 1
        assert p1[0]["task_id"] != p2[0]["task_id"]
        assert p1[0]["task_id"] in created_task_ids
        assert p2[0]["task_id"] in created_task_ids
