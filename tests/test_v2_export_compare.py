"""
Copyright 2026 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

V2 export and compare endpoint tests.
"""

from __future__ import annotations

# pylint: disable=missing-function-docstring,wrong-import-position,wrong-import-order

from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from nw_diff_v2.main import app
from v2_helpers import configure_v2_test_env, write_hosts_csv


def test_v2_export_html_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = tmp_path / "artifacts" / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("output", encoding="utf-8")

    with TestClient(app) as client:
        response = client.get("/api/v2/exports/router1/html")
        assert response.status_code == 200
        assert "NW-Diff v2 Export" in response.text
        assert "router1~show_version.txt" in response.text


def test_v2_export_diff_json_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = tmp_path / "artifacts" / "origin"
    dest_dir = tmp_path / "artifacts" / "dest"
    origin_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (dest_dir / "router1~show_version.txt").write_text("same\n", encoding="utf-8")
    (origin_dir / "router1~show_running-config.txt").write_text("x\n", encoding="utf-8")
    (dest_dir / "router1~show_running-config.txt").write_text("y\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(tmp_path, ["router1,10.0.0.1,admin,22,cisco"])
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

    with TestClient(app) as client:
        response = client.get("/api/v2/exports/%3Cscript%3E")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid hostname"


def test_v2_compare_files_endpoint(tmp_path: Path, monkeypatch) -> None:
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = tmp_path / "artifacts" / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (origin_dir / "router2~show_version.txt").write_text("abd\n", encoding="utf-8")

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
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)

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
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = tmp_path / "artifacts" / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_route_0.0.0.0_0.txt").write_text(
        "via 10.0.0.254\n", encoding="utf-8"
    )
    (origin_dir / "router2~show_route_0.0.0.0_0.txt").write_text(
        "via 10.0.0.1\n", encoding="utf-8"
    )

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
    hosts_csv = write_hosts_csv(
        tmp_path,
        [
            "router1,10.0.0.1,admin,22,cisco",
            "router2,10.0.0.2,admin,22,cisco",
        ],
    )
    configure_v2_test_env(tmp_path, monkeypatch, hosts_csv=hosts_csv)
    origin_dir = tmp_path / "artifacts" / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    (origin_dir / "router1~show_version.txt").write_text("abc\n", encoding="utf-8")
    (origin_dir / "router2~show_version.txt").write_text("abd\n", encoding="utf-8")

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
