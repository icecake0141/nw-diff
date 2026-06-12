"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 end-to-end API flow tests.
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

from nw_diff_v2.domain.models import CaptureTaskStatus
from nw_diff_v2.domain.services.lock_service import release_hosts
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.infra.storage.files import write_output
from nw_diff_v2.main import app
from v2_helpers import (
    configure_v2_test_env,
    reset_v2_command_profiles,
    write_hosts_csv,
)

CAPTURE_QUEUE_LAUNCH = (
    "nw_diff_v2.domain.services.capture_queue_service.launch_capture_task"
)


@pytest.fixture(autouse=True)
def reset_command_profiles(monkeypatch, tmp_path: Path) -> None:
    reset_v2_command_profiles(monkeypatch, tmp_path)


def test_v2_end_to_end_capture_diff_export_retry_flow(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

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

    monkeypatch.setattr(CAPTURE_QUEUE_LAUNCH, _fake_launch_capture_task)

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
