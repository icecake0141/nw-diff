"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,unused-argument,wrong-import-position,import-outside-toplevel,use-implicit-booleaness-not-comparison

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureTaskStatus
from nw_diff_v2.domain.services import capture_service
from nw_diff_v2.domain.services.lock_service import release_hosts
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.infra.storage.files import write_output
from nw_diff_v2.main import app

CAPTURE_QUEUE_LAUNCH = (
    "nw_diff_v2.domain.services.capture_queue_service.launch_capture_task"
)
@pytest.fixture(autouse=True)
def reset_command_profiles(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing-command-profiles.yaml"
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(missing))
    capture_service.validate_command_profile_config()


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
        assert "Current Progress" in response.text
        assert "Ready to start a batch capture" in response.text
        assert "Capture Origin All" in response.text
        assert "Capture Dest All" in response.text
        assert ">Logs</a>" in response.text
        assert "<summary>" in response.text
        assert ">Debug</span>" in response.text
        assert "Lock Status" in response.text
        assert "Readiness" in response.text
        assert "Worker Status" in response.text
        assert "Contract Check" in response.text
        assert "host1,host2" in response.text
        assert "topActionStatus" in response.text
        assert 'id="captureStatusPanel"' in response.text
        assert 'id="captureStatusHeadline"' in response.text
        assert "taskQuickSummary" in response.text
        assert "compareSummary" in response.text
        assert "Live Console" in response.text
        assert 'id="liveConsoleView"' in response.text
        assert 'id="liveConsoleFollowButton"' in response.text
        assert 'id="taskTableWrap"' in response.text
        assert "function startLiveConsole()" in response.text
        assert "function toggleLiveConsoleFollow()" in response.text
        assert "async function selectTask(taskId)" in response.text
        assert "await checkTask();" in response.text
        assert "startLiveConsole();" in response.text
        assert "MAX_CONSOLE_LINES = 2000" in response.text
        assert "RECENT_TASK_REFRESH_MS = 5000" in response.text
        assert '<select id="exportHost">' in response.text
        assert '<select id="diffHost">' in response.text
        assert '<select id="cmpHost1">' in response.text
        assert '<select id="cmpHost2">' in response.text
        compare_heading = response.text.find(">Compare</h2>")
        debug_heading = response.text.find(">Debug</span>")
        assert compare_heading < debug_heading
        assert 'id="compareDisplayModeToggle"' in response.text
        assert "Display: Full (click for Compact)" in response.text
        assert "<h2>Host Diff Summary</h2>" not in response.text
        assert "<h2>Task Inspector</h2>" not in response.text
        assert "Origin Capture Status" in response.text
        assert "Dest Capture Status" in response.text
        assert 'id="compareHtml"' in response.text
        diff_placeholder = (
            "Diff output will appear here after " + "running a comparison."
        )
        assert diff_placeholder in response.text
        assert "<h2>Lock Status</h2>" not in response.text
        assert '<details class="debug-details">' in response.text
        assert "Run the check to load current lock information." in response.text
        assert 'id="taskView"' not in response.text
        assert 'id="streamView"' not in response.text
        assert 'id="taskListView"' not in response.text
        assert "function startLiveStream()" not in response.text
        assert "Open Stream" not in response.text
        assert "Live Stream" not in response.text
        assert "Stop Live" not in response.text
        assert "Recent Tasks" not in response.text
        assert "Start Auto Refresh" not in response.text
        assert "Stop Auto Refresh" not in response.text
        assert "Retry</button>" not in response.text
        assert "Live</button>" not in response.text
        assert 'title="Select this task and open its live console"' in response.text
        assert (
            'title="Request cancellation for this task" onclick="quickCancel('
            in response.text
        )
        assert "loadRecentTasks();" in response.text
        assert "startAutoRefresh();" in response.text
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
        assert "loadWorkerStatus().catch(() => {});" not in response.text
        assert "loadReadinessStatus().catch(() => {});" not in response.text
        assert "loadContractStatus().catch(() => {});" not in response.text
        assert "loadLockStatus();" not in response.text


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
        CAPTURE_QUEUE_LAUNCH, _fake_launch_capture_task
    )
    monkeypatch.setattr(
        CAPTURE_QUEUE_LAUNCH, _fake_launch_capture_task
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
