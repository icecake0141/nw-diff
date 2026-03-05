"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,unused-argument,wrong-import-position,import-outside-toplevel,use-implicit-booleaness-not-comparison

import base64
from pathlib import Path
import sys
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nw_diff_v2.config import Settings, settings
from nw_diff_v2.domain.models import CaptureTaskStatus
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.domain.services.task_worker import process_one_queued_task
from nw_diff_v2.infra.adapters.netmiko_adapter import NetmikoAdapter
from nw_diff_v2.infra.repositories.lock_repo import force_set_lock
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.infra.repositories.task_repo import recover_orphaned_running_tasks
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.storage.files import write_output
from nw_diff_v2.main import app
from nw_diff_v2.security.auth import require_auth


def test_v2_host_repo_skips_invalid_rows(tmp_path: Path) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.999,admin,22,cisco\n"
            "router3,10.0.0.3,admin,70000,cisco\n"
        ),
        encoding="utf-8",
    )

    rows = load_hosts(str(hosts_csv))

    assert len(rows) == 1
    assert rows[0].host == "router1"


def test_v2_host_repo_rejects_xss_like_values(tmp_path: Path) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "<script>alert(1)</script>,10.0.0.1,admin,22,cisco\n"
            "router1,10.0.0.2,admin,22,cisco<script>\n"
            "router2,10.0.0.3,admin<script>,22,cisco\n"
        ),
        encoding="utf-8",
    )

    rows = load_hosts(str(hosts_csv))
    assert rows == []


def test_v2_host_repo_rejects_overlong_values(tmp_path: Path) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    long_host = "h" * 254
    long_user = "u" * 65
    long_model = "m" * 65
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            f"{long_host},10.0.0.1,admin,22,cisco\n"
            f"router1,10.0.0.2,{long_user},22,cisco\n"
            f"router2,10.0.0.3,admin,22,{long_model}\n"
            "router3,10.0.0.4,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )

    rows = load_hosts(str(hosts_csv))
    assert len(rows) == 1
    assert rows[0].host == "router3"


def test_v2_host_repo_accepts_generic_linux_model_with_space(tmp_path: Path) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nlinux01,10.0.0.10,admin,22,Generic Linux\n",
        encoding="utf-8",
    )

    rows = load_hosts(str(hosts_csv))
    assert len(rows) == 1
    assert rows[0].model == "Generic Linux"


def test_v2_lock_service_rejects_same_host(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()
    try:
        acquired, conflicts = try_lock_hosts({"router1"})
        assert acquired is False
        assert conflicts == {"router1"}
    finally:
        release_hosts({"router1"})


def test_v2_lock_service_releases_stale_locks(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "v2_stale.db"
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "host_lock_timeout_seconds", 0.01)
    force_set_lock("router1", time.time() - 1.0)
    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()
    release_hosts({"router1"})


def test_v2_task_repo_uses_sqlite_busy_timeout(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "v2_busy.db"
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    task_repo.init_db()
    with task_repo._connect() as conn:  # pylint: disable=protected-access
        timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout_ms == 3000


def test_v2_startup_cleans_stale_locks(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2_startup.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "host_lock_timeout_seconds", 0.01)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

    force_set_lock("router1", time.time() - 1.0)

    with TestClient(app) as client:
        resp = client.get("/api/v2/system/locks")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["count"] == 0


def test_v2_worker_processes_queued_task(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()

    task_repo.create_task(
        task_id="task-1",
        mode="single",
        base="origin",
        hosts=["router1"],
    )

    def _fake_capture(self, **kwargs):  # noqa: ANN001
        assert kwargs["host"] == "10.0.0.1"
        return {"show version": "ok"}

    monkeypatch.setattr(NetmikoAdapter, "capture_commands", _fake_capture)

    processed = process_one_queued_task()
    assert processed is True

    task = task_repo.get_task("task-1")
    assert task is not None
    assert task["status"] == "completed"
    assert task["result"]["success_count"] == 1
    assert task["result"]["failure_count"] == 0

    reacquired, _ = try_lock_hosts({"router1"})
    assert reacquired is True
    release_hosts({"router1"})


def test_v2_worker_maps_generic_linux_model_to_netmiko_linux(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nlinux01,10.0.0.10,admin,22,Generic Linux\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2_linux.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

    acquired, conflicts = try_lock_hosts({"linux01"})
    assert acquired is True
    assert conflicts == set()

    task_repo.create_task(
        task_id="task-linux-1",
        mode="single",
        base="origin",
        hosts=["linux01"],
    )

    def _fake_capture(self, **kwargs):  # noqa: ANN001
        assert kwargs["device_type"] == "linux"
        assert kwargs["commands"] == ["uname -a", "cat /etc/os-release", "ip addr"]
        return {"uname -a": "Linux test"}

    monkeypatch.setattr(NetmikoAdapter, "capture_commands", _fake_capture)

    processed = process_one_queued_task()
    assert processed is True

    task = task_repo.get_task("task-linux-1")
    assert task is not None
    assert task["status"] == "completed"
    assert task["result"]["success_count"] == 1
    assert task["result"]["failure_count"] == 0

    reacquired, _ = try_lock_hosts({"linux01"})
    assert reacquired is True
    release_hosts({"linux01"})


def test_v2_recover_orphaned_running_tasks(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")

    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()

    task_repo.create_task(
        task_id="task-running",
        mode="single",
        base="origin",
        hosts=["router1"],
    )
    task_repo.update_task(
        "task-running",
        status=CaptureTaskStatus.RUNNING,
        started_at=time.time(),
    )

    recovered = recover_orphaned_running_tasks()
    assert len(recovered) == 1
    assert recovered[0]["task_id"] == "task-running"

    task = task_repo.get_task("task-running")
    assert task is not None
    assert task["status"] == "failed"

    release_hosts(set(recovered[0]["hosts"]))
    reacquired, _ = try_lock_hosts({"router1"})
    assert reacquired is True
    release_hosts({"router1"})


def test_v2_auth_requires_token_outside_development(monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "nw_diff_api_token", "secret")

    require_auth("Bearer secret")

    with pytest.raises(HTTPException):
        require_auth("Bearer wrong")


def test_v2_settings_validate_runtime_requires_api_token_in_production() -> None:
    cfg = Settings(
        env="production",
        device_password="test_password",
        nw_diff_api_token=None,
    )
    with pytest.raises(RuntimeError, match="NW_DIFF_API_TOKEN is required"):
        cfg.validate_runtime()


def test_v2_settings_validate_runtime_allows_no_api_token_in_development() -> None:
    cfg = Settings(
        env="development",
        device_password="test_password",
        nw_diff_api_token=None,
    )
    cfg.validate_runtime()


def test_v2_auth_basic_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "nw_diff_api_token", "secret_token")
    monkeypatch.setattr(settings, "nw_diff_basic_user", "admin")
    monkeypatch.setattr(settings, "nw_diff_basic_password", "adminpass")
    monkeypatch.setattr(settings, "nw_diff_basic_password_hash", None)

    credentials = base64.b64encode(b"admin:adminpass").decode("utf-8")
    require_auth(f"Basic {credentials}")

    bad_credentials = base64.b64encode(b"admin:wrong").decode("utf-8")
    with pytest.raises(HTTPException):
        require_auth(f"Basic {bad_credentials}")


def test_v2_capture_api_creates_task_and_status_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task", _fake_launch_capture_task
    )

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


def test_v2_task_stream_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        from nw_diff_v2.infra.storage.task_logs import append_task_log

        append_task_log(task_id, "line1")
        append_task_log(task_id, "line2")
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": 1, "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task", _fake_launch_capture_task
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": ["router1"]},
        )
        task_id = response.json()["task_id"]

        stream_response = client.get(f"/api/v2/tasks/{task_id}/stream")
        assert stream_response.status_code == 200
        body = stream_response.text
        assert "data: line1" in body
        assert "data: line2" in body
        assert "event: status" in body

        tail_response = client.get(f"/api/v2/tasks/{task_id}/stream?tail_lines=1")
        assert tail_response.status_code == 200
        tail_body = tail_response.text
        assert "data: line2" in tail_body
        assert "data: line1" not in tail_body

        resumed_response = client.get(
            f"/api/v2/tasks/{task_id}/stream",
            headers={"Last-Event-ID": "0"},
        )
        assert resumed_response.status_code == 200
        resumed_body = resumed_response.text
        assert "data: line2" in resumed_body
        assert "data: line1" not in resumed_body


def test_v2_ui_index_renders(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/v2")
        assert response.status_code == 200
        assert "NW-Diff v2 Control Panel" in response.text
        assert "Lock Status" in response.text
        assert "Readiness" in response.text
        assert "host1,host2" in response.text
        assert "topActionStatus" in response.text
        assert "taskQuickSummary" in response.text
        assert "compareSummary" in response.text
        assert '<select id="exportHost">' in response.text
        assert '<select id="diffHost">' in response.text
        assert '<select id="cmpHost1">' in response.text
        assert '<select id="cmpHost2">' in response.text
        assert response.text.find("<h2>Compare</h2>") < response.text.find(
            "<h2>Lock Status</h2>"
        )
        assert 'id="compareDisplayModeToggle"' in response.text
        assert "Display: Full (click for Compact)" in response.text
        assert "<h2>Host Diff Summary</h2>" not in response.text
        assert "Origin取得状況" in response.text
        assert "Dest取得状況" in response.text
        assert 'class="compare-html diff-content"' in response.text
        assert (
            "document.getElementById('workerStatus').textContent = JSON.stringify("
            not in response.text
        )
        assert (
            "document.getElementById('readinessStatus').textContent = JSON.stringify("
            not in response.text
        )
        assert (
            "document.getElementById('contractStatus').textContent = JSON.stringify("
            not in response.text
        )
        assert (
            "document.getElementById('lockStatus').textContent = JSON.stringify("
            not in response.text
        )
        assert (
            "document.getElementById('hostSummaryView').textContent = JSON.stringify("
            not in response.text
        )
        assert "formatWorkerStatus(" in response.text
        assert "formatReadinessStatus(" in response.text
        assert "formatContractStatus(" in response.text
        assert "formatLockStatus(" in response.text
        assert "formatHostSummaryStatus(" in response.text


def test_v2_batch_skip_locked_policy(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "batch_conflict_policy", "skip_locked")

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task", _fake_launch_capture_task
    )

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "batch_conflict_policy", "skip_locked")

    call_count = {"value": 0}

    def _fake_try_lock_hosts(hosts):  # noqa: ANN001
        call_count["value"] += 1
        if call_count["value"] == 1:
            return False, {"router1"}
        return False, {"router2"}

    monkeypatch.setattr("nw_diff_v2.api.capture.try_lock_hosts", _fake_try_lock_hosts)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task", _fake_launch_capture_task
    )

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


def test_v2_export_html_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("output", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/exports/router1/html")
        assert response.status_code == 200
        assert "NW-Diff v2 Export" in response.text
        assert "router1~show_version.txt" in response.text


def test_v2_export_diff_json_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (origin_dir / "router1~show_running-config.txt").write_text("x\n", encoding="utf-8")
    (dest_dir / "router1~show_running-config.txt").write_text("y\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/exports/router1/diff-json")
        assert response.status_code == 200
        payload = response.json()
        assert payload["hostname"] == "router1"
        statuses = {
            item["command_key"]: item["diff_status"] for item in payload["commands"]
        }
        assert statuses["show_version"] == "identical"
        assert statuses["show_running-config"] == "changes detected"


def test_v2_export_rejects_invalid_hostname(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/exports/%3Cscript%3E")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid hostname"


def test_v2_compare_files_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (origin_dir / "router2~show_version.txt").write_text("abd\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "router1",
                "host2": "router2",
                "base": "origin",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "changes detected"
        assert payload["base"] == "origin"


def test_v2_compare_files_rejects_invalid_command(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "router1",
                "host2": "router2",
                "base": "origin",
                "command": "../secret",
                "view": "inline",
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "File for router1 not found"


def test_v2_compare_files_accepts_command_with_slash(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_route_0.0.0.0_0.txt").write_text(
        "via 10.0.0.254\n", encoding="utf-8"
    )
    (origin_dir / "router2~show_route_0.0.0.0_0.txt").write_text(
        "via 10.0.0.1\n", encoding="utf-8"
    )

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "router1",
                "host2": "router2",
                "base": "origin",
                "command": "show route 0.0.0.0/0",
                "view": "inline",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "changes detected"
        assert payload["command"] == "show route 0.0.0.0/0"


def test_v2_compare_files_requires_exact_inventory_hosts(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1-show_version.txt").write_text("abc\n", encoding="utf-8")
    (origin_dir / "router2-show_version.txt").write_text("abd\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "router1-prefix",
                "host2": "router2",
                "base": "origin",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == "Invalid host1: must exactly match an inventory host"
        )

        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "router1",
                "host2": "router2-suffix",
                "base": "origin",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == "Invalid host2: must exactly match an inventory host"
        )

        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "Router1",
                "host2": "router2",
                "base": "origin",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == "Invalid host1: must exactly match an inventory host"
        )

        response = client.post(
            "/api/v2/compare/files",
            json={
                "host1": "router1-prefix",
                "host2": "router2-suffix",
                "base": "origin",
                "command": "show version",
                "view": "inline",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Invalid host1: must exactly match an inventory host, "
            "Invalid host2: must exactly match an inventory host"
        )


def test_v2_diff_host_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (origin_dir / "router1~show_running-config.txt").write_text(
        "line1\n", encoding="utf-8"
    )
    (dest_dir / "router1~show_running-config.txt").write_text(
        "line2\n", encoding="utf-8"
    )

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/diff/router1?view=sidebyside")
        assert response.status_code == 200
        payload = response.json()
        assert payload["hostname"] == "router1"
        assert payload["summary"]["total"] == 2
        assert payload["summary"]["identical"] == 1
        assert payload["summary"]["changed"] == 1


def test_v2_host_detail_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("a\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("b\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/hosts/router1/detail?view=inline&diff_mode=context&context_lines=2"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["hostname"] == "router1"
        assert payload["diff_mode"] == "context"
        assert payload["context_lines"] == 2
        assert payload["summary"]["total"] == 1
        assert payload["summary"]["changed"] == 1
        assert payload["command_results"][0]["command"] == "show version"


def test_v2_host_detail_endpoint_filters(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (origin_dir / "router1~show_running-config.txt").write_text("x\n", encoding="utf-8")
    (dest_dir / "router1~show_running-config.txt").write_text("y\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        changed = client.get("/api/v2/hosts/router1/detail?status_filter=changed")
        assert changed.status_code == 200
        changed_payload = changed.json()
        assert changed_payload["summary"]["total"] == 1
        assert (
            changed_payload["command_results"][0]["command_key"]
            == "show_running-config"
        )

        contains = client.get("/api/v2/hosts/router1/detail?command_contains=version")
        assert contains.status_code == 200
        contains_payload = contains.json()
        assert contains_payload["summary"]["total"] == 1
        assert contains_payload["command_results"][0]["command_key"] == "show_version"


def test_v2_host_isolated_from_prefixed_hostname(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "Host,10.0.0.1,admin,22,cisco\n"
            "Host-TMP,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    (origin_dir / "Host~show_version.txt").write_text("host-origin\n", encoding="utf-8")
    (dest_dir / "Host~show_version.txt").write_text("host-dest\n", encoding="utf-8")
    (origin_dir / "Host-TMP~show_version.txt").write_text(
        "tmp-origin\n", encoding="utf-8"
    )
    (dest_dir / "Host-TMP~show_version.txt").write_text("tmp-dest\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        detail_response = client.get("/api/v2/hosts/Host/detail")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["summary"]["total"] == 1
        assert detail_payload["command_results"][0]["command_key"] == "show_version"

        diff_response = client.get("/api/v2/diff/Host?view=inline")
        assert diff_response.status_code == 200
        diff_payload = diff_response.json()
        assert diff_payload["summary"]["total"] == 1
        assert diff_payload["commands"][0]["command_key"] == "show_version"

        export_response = client.get("/api/v2/exports/Host")
        assert export_response.status_code == 200
        export_payload = export_response.json()
        export_files = {
            item["file"]
            for base in ("origin", "dest")
            for item in export_payload["bases"][base]
        }
        assert export_files == {"Host~show_version.txt"}


def test_v2_hosts_summary_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    (origin_dir / "router1~show_version.txt").write_text("a\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("b\n", encoding="utf-8")
    (origin_dir / "router2~show_version.txt").write_text("same\n", encoding="utf-8")
    (dest_dir / "router2~show_version.txt").write_text("same\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

    task_repo.create_task(
        task_id="sum-task-1",
        mode="single",
        base="origin",
        hosts=["router1"],
    )
    task_repo.update_task(
        "sum-task-1",
        status=CaptureTaskStatus.COMPLETED,
        started_at=1.0,
        finished_at=2.0,
        result={"success_count": 1, "failure_count": 0},
    )
    task_repo.create_task(
        task_id="sum-task-2",
        mode="single",
        base="origin",
        hosts=["router2"],
    )
    task_repo.update_task(
        "sum-task-2",
        status=CaptureTaskStatus.FAILED,
        started_at=3.0,
        finished_at=4.0,
        error="x",
    )

    with TestClient(app) as client:
        response = client.get("/api/v2/hosts/summary?limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 2
        assert payload["rows"][0]["host"] == "router2"
        assert payload["rows"][0]["last_task_status"] == "failed"
        assert payload["rows"][1]["host"] == "router1"
        assert payload["rows"][1]["changed"] == 1
        assert payload["rows"][1]["last_task_status"] == "completed"
        assert isinstance(payload["rows"][1]["commands"], list)
        assert payload["rows"][1]["commands"][0]["command_key"] == "show_version"
        assert payload["rows"][1]["commands"][0]["origin"]["status"] == "captured"
        assert payload["rows"][1]["commands"][0]["origin"]["captured_at"] is not None
        assert payload["rows"][1]["commands"][0]["dest"]["status"] == "captured"
        assert payload["rows"][1]["commands"][0]["dest"]["captured_at"] is not None

        filtered = client.get("/api/v2/hosts/summary?host_contains=router2")
        assert filtered.status_code == 200
        filtered_payload = filtered.json()
        assert filtered_payload["count"] == 1
        assert filtered_payload["rows"][0]["host"] == "router2"

        capped = client.get("/api/v2/hosts/summary?limit=99999")
        assert capped.status_code == 200
        capped_payload = capped.json()
        assert capped_payload["count"] == 2

        non_prioritized = client.get("/api/v2/hosts/summary?prioritize_failed=false")
        assert non_prioritized.status_code == 200
        non_prioritized_payload = non_prioritized.json()
        assert non_prioritized_payload["rows"][0]["host"] == "router1"


def test_v2_hosts_summary_endpoint_command_capture_statuses(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    origin_dir = artifact_root / "origin"
    dest_dir = artifact_root / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    (origin_dir / "router1-show_version.txt").write_text("version\n", encoding="utf-8")
    (dest_dir / "router1-show_clock.txt").write_text("clock\n", encoding="utf-8")

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        task_repo.create_task(
            task_id="sum-task-running-dest",
            mode="single",
            base="dest",
            hosts=["router1"],
        )
        task_repo.update_task(
            "sum-task-running-dest",
            status=CaptureTaskStatus.RUNNING,
            started_at=1.0,
        )
        response = client.get("/api/v2/hosts/summary?limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        command_rows = payload["rows"][0]["commands"]
        by_key = {row["command_key"]: row for row in command_rows}

        show_version = by_key["show_version"]
        assert show_version["origin"]["status"] == "captured"
        assert show_version["origin"]["captured_at"] is not None
        assert show_version["dest"]["status"] == "running"
        assert show_version["dest"]["captured_at"] is None

        show_clock = by_key["show_clock"]
        assert show_clock["origin"]["status"] == "not_captured"
        assert show_clock["origin"]["captured_at"] is None
        assert show_clock["dest"]["status"] == "captured"
        assert show_clock["dest"]["captured_at"] is not None


def test_v2_host_detail_page_renders(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/v2/hosts/router1")
        assert response.status_code == 200
        assert "Host Detail: router1" in response.text
        assert (
            '<option value="sidebyside" selected>sidebyside</option>' in response.text
        )
        assert 'id="displayModeToggle"' in response.text
        assert "Display: Full (click for Compact)" in response.text
        assert "summary-table" in response.text
        assert "diff-content" in response.text


def test_v2_logs_api_app_source(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    app_log = tmp_path / "nw-diff.log"
    app_log.write_text(
        "2026-01-01 INFO hello\n2026-01-01 ERROR boom\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "app_log_path", str(app_log))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/logs?source=app&level=ERROR&limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "app"
        assert payload["count"] == 1
        assert "ERROR boom" in payload["lines"][0]

        contains_response = client.get(
            "/api/v2/logs?source=app&contains=hello&limit=10"
        )
        assert contains_response.status_code == 200
        contains_payload = contains_response.json()
        assert contains_payload["count"] == 1
        assert "INFO hello" in contains_payload["lines"][0]


def test_v2_logs_api_task_source_and_page(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    from nw_diff_v2.infra.storage.task_logs import append_task_log

    append_task_log("task-x", "line-a")
    append_task_log("task-x", "line-b")

    with TestClient(app) as client:
        response = client.get("/api/v2/logs?source=task&task_id=task-x&limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "task"
        assert payload["count"] == 2
        assert payload["lines"][-1] == "line-b"

        contains_response = client.get(
            "/api/v2/logs?source=task&task_id=task-x&contains=line-b&limit=10"
        )
        assert contains_response.status_code == 200
        contains_payload = contains_response.json()
        assert contains_payload["count"] == 1
        assert contains_payload["lines"][0] == "line-b"

        page = client.get("/v2/logs")
        assert page.status_code == 200
        assert "NW-Diff v2 Logs" in page.text
        assert "contains text" in page.text


def test_v2_task_list_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task", _fake_launch_capture_task
    )

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


def test_v2_worker_status_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/system/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["db_url"].startswith("sqlite:///")


def test_v2_system_locks_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    with TestClient(app) as client:
        response = client.get("/api/v2/system/contract")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["missing"] == []


def test_v2_system_readiness_endpoint_ok_and_degraded(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
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


def test_v2_task_cancel_endpoint_sets_flag(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    def _noop_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        # keep task in queued state to test cancellation flag update
        del task_id, base, hosts, reserved_hosts

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task",
        _noop_launch_capture_task,
    )

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

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

    def _noop_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        del task_id, base, hosts, reserved_hosts

    monkeypatch.setattr(
        "nw_diff_v2.api.tasks.launch_capture_task",
        _noop_launch_capture_task,
    )

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

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


def test_v2_end_to_end_capture_diff_export_retry_flow(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "artifact_root", str(artifact_root))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", False)

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        host = hosts[0]["host"]
        output = (
            "show version output (origin)\n"
            if str(base.value) == "origin"
            else "show version output (dest)\n"
        )
        write_output(str(base.value), host, "show version", output)
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task", _fake_launch_capture_task
    )
    monkeypatch.setattr(
        "nw_diff_v2.api.tasks.launch_capture_task", _fake_launch_capture_task
    )

    with TestClient(app) as client:
        origin_resp = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "origin", "hosts": ["router1"]},
        )
        assert origin_resp.status_code == 200
        dest_resp = client.post(
            "/api/v2/captures",
            json={"mode": "single", "base": "dest", "hosts": ["router1"]},
        )
        assert dest_resp.status_code == 200

        diff_resp = client.get("/api/v2/diff/router1?view=inline")
        assert diff_resp.status_code == 200
        diff_payload = diff_resp.json()
        assert diff_payload["summary"]["total"] >= 1
        assert diff_payload["summary"]["changed"] >= 1

        export_resp = client.get("/api/v2/exports/router1")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()
        assert len(export_payload["bases"]["origin"]) >= 1
        assert len(export_payload["bases"]["dest"]) >= 1

        export_diff_resp = client.get("/api/v2/exports/router1/diff-json")
        assert export_diff_resp.status_code == 200
        commands = export_diff_resp.json()["commands"]
        assert any(item["diff_status"] == "changes detected" for item in commands)

        old_task_id = dest_resp.json()["task_id"]
        retry_resp = client.post(f"/api/v2/tasks/{old_task_id}/retry")
        assert retry_resp.status_code == 200
        new_task_id = retry_resp.json()["task_id"]

        new_task = client.get(f"/api/v2/tasks/{new_task_id}")
        assert new_task.status_code == 200
        new_task_payload = new_task.json()
        assert new_task_payload["task_id"] == new_task_id
        assert new_task_payload["hosts"] == ["router1"]


def test_v2_task_list_status_filter(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    release_hosts({"router1", "router2"})

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
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

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task",
        _fake_launch_capture_task,
    )

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


def test_v2_single_mode_requires_exactly_one_host(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

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
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
            "router3,10.0.0.3,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    captured_hosts: list[list[str]] = []

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        captured_hosts.append(sorted([h["host"] for h in hosts]))
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task",
        _fake_launch_capture_task,
    )

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


def test_v2_task_list_supports_offset(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        (
            "host,ip,username,port,model\n"
            "router1,10.0.0.1,admin,22,cisco\n"
            "router2,10.0.0.2,admin,22,cisco\n"
            "router3,10.0.0.3,admin,22,cisco\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "v2.db"
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)

    def _fake_launch_capture_task(
        *, task_id, base, hosts, reserved_hosts
    ):  # noqa: ANN001
        task_repo.update_task(
            task_id,
            status=CaptureTaskStatus.COMPLETED,
            started_at=1.0,
            finished_at=2.0,
            result={"success_count": len(hosts), "failure_count": 0},
        )
        release_hosts(reserved_hosts)

    monkeypatch.setattr(
        "nw_diff_v2.api.capture.launch_capture_task",
        _fake_launch_capture_task,
    )

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
