"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 UI rendering tests.
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

from nw_diff_v2.main import app
from v2_helpers import (
    configure_v2_test_env,
    reset_v2_command_profiles,
    write_hosts_csv,
)


@pytest.fixture(autouse=True)
def reset_command_profiles(monkeypatch, tmp_path: Path) -> None:
    reset_v2_command_profiles(monkeypatch, tmp_path)


def test_v2_ui_index_renders(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

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
