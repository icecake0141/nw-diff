"""Tests for command profile override loading and validation."""

from __future__ import annotations

# pylint: disable=missing-function-docstring,protected-access,wrong-import-position

from collections.abc import Generator
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services import capture_service


@pytest.fixture(autouse=True)
def reset_command_profile_state(
    monkeypatch, tmp_path: Path
) -> Generator[None, None, None]:
    """Reset active command profile config to defaults after each test."""
    missing = tmp_path / "missing.override.yaml"
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(missing))
    capture_service.validate_command_profile_config()
    yield
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(missing))
    capture_service.validate_command_profile_config()


def test_uses_defaults_when_override_is_missing(monkeypatch, tmp_path: Path) -> None:
    override_path = tmp_path / "not_found.yaml"
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(override_path))

    capture_service.validate_command_profile_config()

    assert capture_service._commands_for_model("cisco") == [
        "show version",
        "show running-config",
    ]
    assert capture_service._commands_for_model("Generic Linux") == [
        "uname -a",
        "cat /etc/os-release",
        "ip addr",
    ]


def test_override_replaces_defaults_and_aliases(monkeypatch, tmp_path: Path) -> None:
    override_path = tmp_path / "device_commands.override.yaml"
    override_path.write_text(
        "\n".join(
            [
                "model_aliases:",
                "  generic linux: linux",
                "command_profiles:",
                "  linux:",
                "    - hostname",
                "    - hostname",
                "default_commands:",
                "  - show clock",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(override_path))

    capture_service.validate_command_profile_config()

    assert capture_service._commands_for_model("Generic Linux") == ["hostname"]
    assert capture_service._commands_for_model("cisco") == ["show clock"]
    assert capture_service._device_type_for_model("Generic Linux") == "linux"


def test_invalid_yaml_fails_fast(monkeypatch, tmp_path: Path) -> None:
    override_path = tmp_path / "invalid.yaml"
    override_path.write_text("command_profiles: [", encoding="utf-8")
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(override_path))

    with pytest.raises(RuntimeError, match="Invalid YAML"):
        capture_service.validate_command_profile_config()


def test_unknown_top_level_key_fails_fast(monkeypatch, tmp_path: Path) -> None:
    override_path = tmp_path / "invalid.yaml"
    override_path.write_text(
        "\n".join(
            [
                "command_profiles:",
                "  cisco:",
                "    - show version",
                "default_commands:",
                "  - show version",
                "unexpected_key: true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(override_path))

    with pytest.raises(RuntimeError, match="Unknown top-level key"):
        capture_service.validate_command_profile_config()


def test_control_character_command_fails_fast(monkeypatch, tmp_path: Path) -> None:
    override_path = tmp_path / "invalid.yaml"
    override_path.write_text(
        "\n".join(
            [
                "command_profiles:",
                "  cisco:",
                "    - |",
                "      show version",
                "      show run",
                "default_commands:",
                "  - show version",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(override_path))

    with pytest.raises(RuntimeError, match="control characters"):
        capture_service.validate_command_profile_config()


def test_required_keys_missing_fails_fast(monkeypatch, tmp_path: Path) -> None:
    override_path = tmp_path / "invalid.yaml"
    override_path.write_text(
        "\n".join(
            [
                "model_aliases:",
                "  generic linux: linux",
                "command_profiles:",
                "  linux:",
                "    - uname -a",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "command_profiles_override_yaml", str(override_path))

    with pytest.raises(
        RuntimeError,
        match="requires both 'command_profiles' and 'default_commands'",
    ):
        capture_service.validate_command_profile_config()
