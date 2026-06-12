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


def _assert_main_ui_sections(html: str) -> None:
    assert "NW-Diff v2 Control Panel" in html
    assert "Current Progress" in html
    assert "Ready to start a batch capture" in html
    assert "Capture Origin All" in html
    assert "Capture Dest All" in html
    assert ">Logs</a>" in html
    assert "Lock Status" in html
    assert "Readiness" in html
    assert "Worker Status" in html
    assert "Contract Check" in html
    assert "Live Console" in html


def _assert_main_ui_ids(html: str) -> None:
    assert 'class="section-jump"' in html
    assert 'href="#section-hosts"' in html
    assert 'href="#section-tasks"' in html
    assert 'href="#section-console"' in html
    assert 'href="#section-export"' in html
    assert 'href="#section-compare"' in html
    assert 'href="#section-diagnostics"' in html
    assert 'id="section-hosts"' in html
    assert 'id="section-tasks"' in html
    assert 'id="section-console"' in html
    assert 'id="section-export"' in html
    assert 'id="section-compare"' in html
    assert 'id="section-diagnostics"' in html
    assert "topActionStatus" in html
    assert 'id="captureStatusPanel"' in html
    assert 'id="captureStatusHeadline"' in html
    assert "taskQuickSummary" in html
    assert "compareSummary" in html
    assert 'id="liveConsoleView"' in html
    assert 'id="liveConsoleFollowButton"' in html
    assert 'id="taskTableWrap"' in html
    assert '<select id="exportHost">' in html
    assert '<select id="diffHost">' in html
    assert '<select id="cmpHost1">' in html
    assert '<select id="cmpHost2">' in html
    assert 'id="compareDisplayModeToggle"' in html
    assert 'id="compareHtml"' in html


def _assert_debug_section(html: str) -> None:
    assert "<summary>" in html
    assert ">Debug</span>" in html
    assert "host1,host2" in html
    assert "<h2>Lock Status</h2>" not in html
    assert '<details class="debug-details">' in html
    assert "Run the check to load current lock information." in html


def _assert_legacy_ui_removed(html: str) -> None:
    assert "<h2>Host Diff Summary</h2>" not in html
    assert "<h2>Task Inspector</h2>" not in html
    assert 'id="taskView"' not in html
    assert 'id="streamView"' not in html
    assert 'id="taskListView"' not in html
    assert "Open Stream" not in html
    assert "Live Stream" not in html
    assert "Stop Live" not in html
    assert "Recent Tasks" not in html
    assert "Start Auto Refresh" not in html
    assert "Stop Auto Refresh" not in html
    assert "Retry</button>" not in html
    assert "Live</button>" not in html


def _assert_external_assets(html: str, js: str, css: str) -> None:
    assert '<link rel="stylesheet" href="/v2/static/index.css">' in html
    assert '<script src="/v2/static/index.js"></script>' in html
    assert "function startLiveConsole()" in js
    assert "function toggleLiveConsoleFollow()" in js
    assert "async function selectTask(taskId)" in js
    assert "await checkTask();" in js
    assert "startLiveConsole();" in js
    assert "MAX_CONSOLE_LINES = 2000" in js
    assert "RECENT_TASK_REFRESH_MS = 5000" in js
    assert "formatWorkerStatus(" in js
    assert "formatReadinessStatus(" in js
    assert "formatContractStatus(" in js
    assert "formatLockStatus(" in js
    assert "formatHostSummaryStatus(" in js
    assert "Origin Capture Status" in js
    assert "Dest Capture Status" in js
    assert "function startLiveStream()" not in js
    assert "loadWorkerStatus().catch(() => {});" not in js
    assert "loadReadinessStatus().catch(() => {});" not in js
    assert "loadContractStatus().catch(() => {});" not in js
    assert "loadLockStatus();" not in js
    assert ".debug-details" in css
    assert ".section-jump" in css


def test_v2_ui_index_renders(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/v2")
        assert response.status_code == 200
        html = response.text
        js_response = client.get("/v2/static/index.js")
        css_response = client.get("/v2/static/index.css")
        assert js_response.status_code == 200
        assert css_response.status_code == 200

        _assert_main_ui_sections(html)
        _assert_main_ui_ids(html)
        _assert_debug_section(html)
        _assert_legacy_ui_removed(html)
        _assert_external_assets(html, js_response.text, css_response.text)

        compare_heading = html.find(">Compare</h2>")
        debug_heading = html.find(">Debug</span>")
        assert compare_heading < debug_heading
        assert "Display: Full (click for Compact)" in html
        diff_placeholder = (
            "Diff output will appear here after " + "running a comparison."
        )
        assert diff_placeholder in html
        assert 'title="Select this task and open its live console"' in js_response.text
        assert (
            'title="Request cancellation for this task" onclick="quickCancel('
            in js_response.text
        )
        assert "loadRecentTasks();" in js_response.text
        assert "startAutoRefresh();" in js_response.text
        assert (
            "document.getElementById('workerStatus').textContent = JSON.stringify("
            not in js_response.text
        )
        assert (
            "document.getElementById('readinessStatus').textContent = JSON.stringify("
            not in js_response.text
        )
        assert (
            "document.getElementById('contractStatus').textContent = JSON.stringify("
            not in js_response.text
        )
        assert (
            "document.getElementById('lockStatus').textContent = JSON.stringify("
            not in js_response.text
        )
        assert (
            "document.getElementById('hostSummaryView').textContent = JSON.stringify("
            not in js_response.text
        )
