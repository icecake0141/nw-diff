"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Core v2 repository, lock, and auth behavior tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position,use-implicit-booleaness-not-comparison

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
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.lock_repo import force_set_lock
from nw_diff_v2.infra.repositories.sqlite import connect
from nw_diff_v2.infra.repositories.task_repo import recover_orphaned_running_tasks
from nw_diff_v2.main import app
from nw_diff_v2.security.auth import require_auth


def _write_hosts_csv(tmp_path: Path, rows: list[str]) -> Path:
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return hosts_csv


def _configure_v2_test_env(
    tmp_path: Path,
    monkeypatch,
    *,
    hosts_csv: Path,
    task_worker_enabled: bool = False,
) -> None:
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{tmp_path / 'v2.db'}")
    monkeypatch.setattr(settings, "artifact_root", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", task_worker_enabled)


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
    with connect() as conn:
        timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout_ms == 3000


def test_v2_startup_cleans_stale_locks(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = _write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    _configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    monkeypatch.setattr(settings, "host_lock_timeout_seconds", 0.01)

    force_set_lock("router1", time.time() - 1.0)

    with TestClient(app) as client:
        resp = client.get("/api/v2/system/locks")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["count"] == 0


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
