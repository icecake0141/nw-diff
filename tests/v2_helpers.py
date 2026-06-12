"""Shared helpers for v2 tests."""

from __future__ import annotations

from pathlib import Path

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services import capture_service


def write_hosts_csv(tmp_path: Path, rows: list[str]) -> Path:
    """Write a v2 hosts.csv file for tests."""
    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        "host,ip,username,port,model\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return hosts_csv


def reset_v2_command_profiles(monkeypatch, tmp_path: Path) -> None:
    """Reset command profile overrides to the default bundled config."""
    missing = tmp_path / "missing-command-profiles.yaml"
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(missing))
    capture_service.validate_command_profile_config()


def configure_v2_test_env(
    tmp_path: Path,
    monkeypatch,
    *,
    hosts_csv: Path,
    task_worker_enabled: bool = False,
) -> None:
    """Patch settings for an isolated v2 test environment."""
    monkeypatch.setattr(settings, "hosts_csv", str(hosts_csv))
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{tmp_path / 'v2.db'}")
    monkeypatch.setattr(settings, "artifact_root", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "device_password", "test_password")
    monkeypatch.setattr(settings, "nw_diff_api_token", None)
    monkeypatch.setattr(settings, "task_worker_enabled", task_worker_enabled)
