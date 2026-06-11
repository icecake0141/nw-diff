"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 queue worker execution tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,unused-argument,wrong-import-position,wrong-import-order,import-outside-toplevel

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services import capture_service
from nw_diff_v2.domain.services.lock_service import release_hosts, try_lock_hosts
from nw_diff_v2.domain.services.task_worker import process_one_queued_task
from nw_diff_v2.infra.adapters.netmiko_adapter import NetmikoAdapter
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.infra.storage.files import ArtifactStorageError
from v2_helpers import configure_v2_test_env, write_hosts_csv


@pytest.fixture(autouse=True)
def reset_command_profiles(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing-command-profiles.yaml"
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(missing))
    capture_service.validate_command_profile_config()


def test_v2_worker_processes_queued_task(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

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
    result = task["result"]
    assert result is not None
    assert result["success_count"] == 1
    assert result["failure_count"] == 0

    from nw_diff_v2.infra.storage.task_logs import task_log_path

    task_log_text = task_log_path("task-1").read_text(encoding="utf-8")
    assert "CMD_START host=router1 command=show version" in task_log_text
    assert "CMD_PREVIEW host=router1 command=show version line=1: ok" in task_log_text
    assert "CMD_END host=router1 command=show version bytes=2" in task_log_text

    reacquired, _ = try_lock_hosts({"router1"})
    assert reacquired is True
    release_hosts({"router1"})


def test_v2_worker_records_artifact_storage_failure(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()

    task_repo.create_task(
        task_id="task-artifact-failure",
        mode="single",
        base="origin",
        hosts=["router1"],
    )

    def _fake_capture(self, **kwargs):  # noqa: ANN001
        assert kwargs["host"] == "10.0.0.1"
        return {"show version": "ok"}

    def _fail_write_output(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ArtifactStorageError("disk full")

    monkeypatch.setattr(NetmikoAdapter, "capture_commands", _fake_capture)
    monkeypatch.setattr(capture_service, "write_output", _fail_write_output)

    processed = process_one_queued_task()
    assert processed is True

    task = task_repo.get_task("task-artifact-failure")
    assert task is not None
    assert task["status"] == "failed"
    assert task["error"] is None
    result = task["result"]
    assert result is not None
    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert result["hosts"][0]["status"] == "failed"
    assert "disk full" in result["hosts"][0]["error"]

    reacquired, _ = try_lock_hosts({"router1"})
    assert reacquired is True
    release_hosts({"router1"})


def test_v2_worker_logs_command_preview_with_limits(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    acquired, conflicts = try_lock_hosts({"router1"})
    assert acquired is True
    assert conflicts == set()

    task_repo.create_task(
        task_id="task-preview",
        mode="single",
        base="origin",
        hosts=["router1"],
    )

    long_line = "A" * 250
    output = "\n".join(["line-1", long_line, "line-3", "line-4"])

    def _fake_capture(self, **kwargs):  # noqa: ANN001
        _ = kwargs
        return {"show version": output}

    monkeypatch.setattr(NetmikoAdapter, "capture_commands", _fake_capture)

    processed = process_one_queued_task()
    assert processed is True

    from nw_diff_v2.infra.storage.task_logs import task_log_path

    task_log_lines = (
        task_log_path("task-preview").read_text(encoding="utf-8").splitlines()
    )
    preview_lines = [line for line in task_log_lines if "CMD_PREVIEW " in line]
    assert len(preview_lines) == 3
    assert "line=1: line-1" in preview_lines[0]
    assert "line=2: " in preview_lines[1]
    assert preview_lines[1].endswith("...")
    assert "line=3: line-3" in preview_lines[2]
    assert "line-4" not in "\n".join(preview_lines)

    reacquired, _ = try_lock_hosts({"router1"})
    assert reacquired is True
    release_hosts({"router1"})


def test_v2_worker_maps_generic_linux_model_to_netmiko_linux(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["linux01,10.0.0.10,admin,22,Generic Linux"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

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
    result = task["result"]
    assert result is not None
    assert result["success_count"] == 1
    assert result["failure_count"] == 0

    reacquired, _ = try_lock_hosts({"linux01"})
    assert reacquired is True
    release_hosts({"linux01"})
