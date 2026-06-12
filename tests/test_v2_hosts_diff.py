"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 host detail, summary, and diff endpoint tests.
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
from nw_diff_v2.infra.repositories import task_repo
from nw_diff_v2.main import app
from v2_helpers import configure_v2_test_env, write_hosts_csv


def _artifact_dir(tmp_path: Path, base: str) -> Path:
    path = tmp_path / "artifacts" / base
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_v2_diff_host_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = _artifact_dir(tmp_path, "origin")
    dest_dir = _artifact_dir(tmp_path, "dest")
    (origin_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (origin_dir / "router1~show_running-config.txt").write_text(
        "line1\n", encoding="utf-8"
    )
    (dest_dir / "router1~show_running-config.txt").write_text(
        "line2\n", encoding="utf-8"
    )

    with TestClient(app) as client:
        response = client.get("/api/v2/diff/router1?view=sidebyside")
        assert response.status_code == 200
        payload = response.json()
        assert payload["hostname"] == "router1"
        assert payload["summary"]["total"] == 2
        assert payload["summary"]["identical"] == 1
        assert payload["summary"]["changed"] == 1


def test_v2_host_detail_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = _artifact_dir(tmp_path, "origin")
    dest_dir = _artifact_dir(tmp_path, "dest")
    (origin_dir / "router1~show_version.txt").write_text("a\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("b\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = _artifact_dir(tmp_path, "origin")
    dest_dir = _artifact_dir(tmp_path, "dest")
    (origin_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (origin_dir / "router1~show_running-config.txt").write_text("x\n", encoding="utf-8")
    (dest_dir / "router1~show_running-config.txt").write_text("y\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(
        tmp_path,
        ["Host,10.0.0.1,admin,22,cisco", "Host-TMP,10.0.0.2,admin,22,cisco"],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = _artifact_dir(tmp_path, "origin")
    dest_dir = _artifact_dir(tmp_path, "dest")
    (origin_dir / "Host~show_version.txt").write_text("host-origin\n", encoding="utf-8")
    (dest_dir / "Host~show_version.txt").write_text("host-dest\n", encoding="utf-8")
    (origin_dir / "Host-TMP~show_version.txt").write_text(
        "tmp-origin\n", encoding="utf-8"
    )
    (dest_dir / "Host-TMP~show_version.txt").write_text("tmp-dest\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = _artifact_dir(tmp_path, "origin")
    dest_dir = _artifact_dir(tmp_path, "dest")
    (origin_dir / "router1~show_version.txt").write_text("a\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("b\n", encoding="utf-8")
    (origin_dir / "router2~show_version.txt").write_text("same\n", encoding="utf-8")
    (dest_dir / "router2~show_version.txt").write_text("same\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = _artifact_dir(tmp_path, "origin")
    dest_dir = _artifact_dir(tmp_path, "dest")
    (origin_dir / "router1~show_version.txt").write_text("version\n", encoding="utf-8")
    (dest_dir / "router1~show_clock.txt").write_text("clock\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/v2/hosts/router1")
        assert response.status_code == 200
        assert "Host Detail" in response.text
        assert ">router1</h1>" in response.text
        assert "Filters and Summary" in response.text
        assert "Command Results" in response.text
        assert (
            '<option value="sidebyside" selected>sidebyside</option>' in response.text
        )
        assert 'id="displayModeToggle"' in response.text
        assert "Display: Full (click for Compact)" in response.text
        assert "summary-table" in response.text
        assert "diff-content" in response.text
        assert "Back to Control Panel" in response.text


def test_v2_index_host_detail_renders_standard_link(
    tmp_path: Path, monkeypatch
) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/v2")
        assert response.status_code == 200
        script_response = client.get("/v2/static/index.js")
        assert script_response.status_code == 200
        assert (
            "href=\"/v2/hosts/' + encodeURIComponent(r.host) + '\">Detail</a>"
            in script_response.text
        )
        assert (
            "window.open('/v2/hosts/' + encodeURIComponent(host), '_blank');"
            not in script_response.text
        )
        assert 'onclick="openHostDetail(' not in script_response.text
