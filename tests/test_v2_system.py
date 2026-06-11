"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 system endpoint tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position,wrong-import-order

from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureTaskStatus
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.infra.repositories.lock_repo import force_set_lock
from nw_diff_v2.main import app
from v2_helpers import configure_v2_test_env, write_hosts_csv


def test_v2_worker_status_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    task_repo.create_task(
        task_id="task-status-1",
        mode="single",
        base="origin",
        hosts=["router1"],
    )
    task_repo.create_task(
        task_id="task-status-2",
        mode="single",
        base="origin",
        hosts=["router1"],
    )
    task_repo.update_task(
        "task-status-2",
        status=CaptureTaskStatus.COMPLETED,
        started_at=1.0,
        finished_at=2.0,
        result={"success_count": 1, "failure_count": 0},
    )

    with TestClient(app) as client:
        response = client.get("/api/v2/system/worker")
        assert response.status_code == 200
        payload = response.json()
        assert payload["queued"] >= 1
        assert payload["completed"] >= 1
        assert payload["locked_hosts"] >= 0
        assert payload["total"] >= 2


def test_v2_system_health_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/api/v2/system/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["db_url"].startswith("sqlite:///")


def test_v2_system_locks_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        task_repo.create_task(
            task_id="running-lock-owner",
            mode="single",
            base="origin",
            hosts=["router1"],
        )
        task_repo.update_task(
            "running-lock-owner",
            status=CaptureTaskStatus.RUNNING,
            started_at=1.0,
        )
        acquired, conflicts = try_lock_hosts({"router1"})
        assert acquired is True
        assert conflicts == set()
        try:
            response = client.get("/api/v2/system/locks")
            assert response.status_code == 200
            payload = response.json()
            assert payload["count"] >= 1
            assert payload["timeout_seconds"] >= 0
            assert payload["locks"][0]["host"] == "router1"
            assert payload["locks"][0]["age_seconds"] >= 0
            assert isinstance(payload["locks"][0]["is_stale"], bool)
            assert payload["locks"][0]["owner_task_ids"] == ["running-lock-owner"]
        finally:
            release_hosts({"router1"})


def test_v2_system_locks_cleanup_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    monkeypatch.setattr(settings, "host_lock_timeout_seconds", 0.01)

    with TestClient(app) as client:
        force_set_lock("router1", time.time() - 1.0)
        before = client.get("/api/v2/system/locks")
        assert before.status_code == 200
        assert before.json()["count"] == 1

        response = client.post("/api/v2/system/locks/cleanup")
        assert response.status_code == 200
        payload = response.json()
        assert payload["deleted"] == 1
        assert payload["remaining"] == 0


def test_v2_system_locks_cleanup_noop_when_timeout_zero(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    monkeypatch.setattr(settings, "host_lock_timeout_seconds", 0.0)

    force_set_lock("router1", time.time() - 1.0)

    with TestClient(app) as client:
        response = client.post("/api/v2/system/locks/cleanup")
        assert response.status_code == 200
        payload = response.json()
        assert payload["deleted"] == 0
        assert payload["remaining"] == 1

    release_hosts({"router1"})


def test_v2_system_locks_release_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    acquired, conflicts = try_lock_hosts({"router1", "router2"})
    assert acquired is True
    assert conflicts == set()

    with TestClient(app) as client:
        release_resp = client.post(
            "/api/v2/system/locks/release",
            json={"hosts": ["router1"]},
        )
        assert release_resp.status_code == 200
        payload = release_resp.json()
        assert payload["released"] == ["router1"]
        assert payload["not_locked"] == []
        assert payload["remaining"] == 1

        not_locked_resp = client.post(
            "/api/v2/system/locks/release",
            json={"hosts": ["router9"]},
        )
        assert not_locked_resp.status_code == 200
        not_locked_payload = not_locked_resp.json()
        assert not_locked_payload["released"] == []
        assert not_locked_payload["not_locked"] == ["router9"]
        assert not_locked_payload["remaining"] == 1

        invalid_resp = client.post(
            "/api/v2/system/locks/release",
            json={"hosts": ["../bad"]},
        )
        assert invalid_resp.status_code == 400
        assert "Invalid host(s)" in invalid_resp.json()["detail"]

        empty_resp = client.post(
            "/api/v2/system/locks/release",
            json={"hosts": []},
        )
        assert empty_resp.status_code == 400
        assert empty_resp.json()["detail"] == "hosts is required"

    release_hosts({"router2"})


def test_v2_system_routes_endpoint_contains_required_routes(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/api/v2/system/routes")
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] > 0
        route_keys = {
            (route["path"], tuple(route["methods"])) for route in payload["routes"]
        }
        required = {
            ("/api/v2/captures", ("POST",)),
            ("/api/v2/tasks", ("GET",)),
            ("/api/v2/tasks/{task_id}", ("GET",)),
            ("/api/v2/tasks/{task_id}/cancel", ("POST",)),
            ("/api/v2/tasks/{task_id}/retry", ("POST",)),
            ("/api/v2/tasks/{task_id}/stream", ("GET",)),
            ("/api/v2/compare/files", ("POST",)),
            ("/api/v2/diff/{hostname}", ("GET",)),
            ("/api/v2/hosts/summary", ("GET",)),
            ("/api/v2/hosts/{hostname}/detail", ("GET",)),
            ("/api/v2/exports/{hostname}", ("GET",)),
            ("/api/v2/exports/{hostname}/html", ("GET",)),
            ("/api/v2/logs", ("GET",)),
            ("/api/v2/system/worker", ("GET",)),
            ("/api/v2/system/health", ("GET",)),
            ("/api/v2/system/readiness", ("GET",)),
            ("/api/v2/system/locks", ("GET",)),
            ("/api/v2/system/locks/cleanup", ("POST",)),
            ("/api/v2/system/locks/release", ("POST",)),
            ("/api/v2/system/routes", ("GET",)),
            ("/api/v2/system/contract", ("GET",)),
        }
        for key in required:
            assert key in route_keys


def test_v2_system_contract_endpoint_has_no_missing_routes(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/api/v2/system/contract")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["missing"] == []


def test_v2_system_readiness_endpoint_ok_and_degraded(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        ok_resp = client.get("/api/v2/system/readiness")
        assert ok_resp.status_code == 200
        ok_payload = ok_resp.json()
        assert ok_payload["status"] == "ok"
        assert ok_payload["counts"]["locked_hosts"] >= 0

        task_repo.create_task(
            task_id="q1",
            mode="single",
            base="origin",
            hosts=["router1"],
        )
        monkeypatch.setattr(settings, "readiness_max_queued", 0)

        degraded_resp = client.get("/api/v2/system/readiness")
        assert degraded_resp.status_code == 200
        degraded_payload = degraded_resp.json()
        assert degraded_payload["status"] == "degraded"
        queue_check = next(
            check
            for check in degraded_payload["checks"]
            if check["name"] == "queue_depth"
        )
        assert queue_check["ok"] is False


def test_v2_system_readiness_degraded_by_lock_depth(
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
    monkeypatch.setattr(settings, "readiness_max_locked", 0)

    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v2/system/readiness")
            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "degraded"
            lock_check = next(
                check for check in payload["checks"] if check["name"] == "lock_depth"
            )
            assert lock_check["ok"] is False
    finally:
        release_hosts({"router1"})
