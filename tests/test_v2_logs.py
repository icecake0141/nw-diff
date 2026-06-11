"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 log endpoint and page tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position,wrong-import-order,import-outside-toplevel

from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from nw_diff_v2.config import settings
from nw_diff_v2.main import app
from v2_helpers import configure_v2_test_env, write_hosts_csv


def test_v2_logs_api_app_source(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    app_log = tmp_path / "nw-diff.log"
    app_log.write_text(
        "2026-01-01 INFO hello\n2026-01-01 ERROR boom\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "app_log_path", str(app_log))

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
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

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
        assert "Filters" in page.text
        assert "Log Output" in page.text
        assert "Back to Control Panel" in page.text
