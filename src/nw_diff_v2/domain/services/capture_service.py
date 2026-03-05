"""Capture task execution service for v2."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import yaml

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureBase, CaptureTaskStatus
from nw_diff_v2.domain.services.lock_service import release_hosts
from nw_diff_v2.infra.adapters.netmiko_adapter import NetmikoAdapter
from nw_diff_v2.infra.repositories.task_repo import is_cancel_requested, update_task
from nw_diff_v2.infra.storage.files import write_output
from nw_diff_v2.infra.storage.task_logs import append_task_log

DEFAULT_COMMAND_PROFILES: dict[str, tuple[str, ...]] = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
    "linux": (
        "uname -a",
        "cat /etc/os-release",
        "ip addr",
    ),
}
DEFAULT_COMMANDS = ("show version",)
DEFAULT_MODEL_ALIASES: dict[str, str] = {
    "generic linux": "linux",
    "generic_linux": "linux",
}
MODEL_KEY_RE = re.compile(r"^[a-zA-Z0-9_ -]+$")
SUPPORTED_OVERRIDE_KEYS = {"model_aliases", "command_profiles", "default_commands"}
ACTIVE_COMMAND_PROFILES = dict(DEFAULT_COMMAND_PROFILES)
ACTIVE_DEFAULT_COMMANDS = list(DEFAULT_COMMANDS)
ACTIVE_MODEL_ALIASES = dict(DEFAULT_MODEL_ALIASES)
logger = logging.getLogger("nw-diff-v2")


def _normalize_model(value: str) -> str:
    return value.strip().lower()


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _validate_command(command: Any, *, context: str) -> str:
    if not isinstance(command, str):
        raise RuntimeError(f"{context} must contain only string commands")
    normalized = command.strip()
    if not normalized:
        raise RuntimeError(f"{context} must not contain empty command")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise RuntimeError(
            f"{context} contains control characters and is not allowed: {normalized!r}"
        )
    return normalized


def _validate_model_key(key: Any, *, context: str) -> str:
    if not isinstance(key, str):
        raise RuntimeError(f"{context} keys must be strings")
    normalized = _normalize_model(key)
    if not normalized:
        raise RuntimeError(f"{context} keys must not be empty")
    if not MODEL_KEY_RE.match(normalized):
        raise RuntimeError(f"{context} has invalid key: {key!r}")
    return normalized


def _load_override_profiles(
    override_path: Path,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...], dict[str, str]]:
    try:
        raw_text = override_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Failed to read command profile override: {override_path}"
        ) from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise RuntimeError(
            f"Invalid YAML in command profile override: {override_path}"
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeError(
            f"Command profile override must be a mapping: {override_path}"
        )

    unknown_keys = set(raw.keys()).difference(SUPPORTED_OVERRIDE_KEYS)
    if unknown_keys:
        raise RuntimeError(
            "Unknown top-level key(s) in command profile override: "
            + ", ".join(sorted(str(key) for key in unknown_keys))
        )

    if "command_profiles" not in raw or "default_commands" not in raw:
        raise RuntimeError(
            "Command profile override requires both 'command_profiles' and "
            "'default_commands'"
        )

    raw_profiles = raw["command_profiles"]
    if not isinstance(raw_profiles, dict):
        raise RuntimeError("'command_profiles' must be a mapping")

    parsed_profiles: dict[str, tuple[str, ...]] = {}
    for profile_key, profile_commands in raw_profiles.items():
        normalized_key = _validate_model_key(profile_key, context="command_profiles")
        if not isinstance(profile_commands, list):
            raise RuntimeError(
                f"command_profiles[{profile_key!r}] must be a list of commands"
            )
        parsed_commands = _dedupe_keep_order(
            [
                _validate_command(
                    command,
                    context=f"command_profiles[{profile_key!r}]",
                )
                for command in profile_commands
            ]
        )
        parsed_profiles[normalized_key] = tuple(parsed_commands)

    raw_default = raw["default_commands"]
    if not isinstance(raw_default, list):
        raise RuntimeError("'default_commands' must be a list of commands")
    parsed_default = tuple(
        _dedupe_keep_order(
            [
                _validate_command(command, context="default_commands")
                for command in raw_default
            ]
        )
    )

    raw_aliases = raw.get("model_aliases", {})
    if not isinstance(raw_aliases, dict):
        raise RuntimeError("'model_aliases' must be a mapping")
    parsed_aliases: dict[str, str] = {}
    for source, destination in raw_aliases.items():
        source_key = _validate_model_key(source, context="model_aliases")
        destination_key = _validate_model_key(destination, context="model_aliases")
        parsed_aliases[source_key] = destination_key

    if not parsed_profiles:
        raise RuntimeError("'command_profiles' must not be empty")
    if not parsed_default:
        raise RuntimeError("'default_commands' must not be empty")

    return parsed_profiles, parsed_default, parsed_aliases


def validate_command_profile_config() -> None:
    """Load command profile config and fail fast on invalid override settings."""
    override_path = Path(settings.command_profiles_override_yaml)
    if not override_path.exists():
        ACTIVE_COMMAND_PROFILES.clear()
        ACTIVE_COMMAND_PROFILES.update(DEFAULT_COMMAND_PROFILES)
        ACTIVE_MODEL_ALIASES.clear()
        ACTIVE_MODEL_ALIASES.update(DEFAULT_MODEL_ALIASES)
        ACTIVE_DEFAULT_COMMANDS.clear()
        ACTIVE_DEFAULT_COMMANDS.extend(DEFAULT_COMMANDS)
        return

    profiles, default_commands, aliases = _load_override_profiles(override_path)
    ACTIVE_COMMAND_PROFILES.clear()
    ACTIVE_COMMAND_PROFILES.update(profiles)
    ACTIVE_MODEL_ALIASES.clear()
    ACTIVE_MODEL_ALIASES.update(aliases)
    ACTIVE_DEFAULT_COMMANDS.clear()
    ACTIVE_DEFAULT_COMMANDS.extend(default_commands)


def _commands_for_model(model: str) -> list[str]:
    """Return the command profile for a device model."""
    normalized_input = _normalize_model(model)
    normalized = ACTIVE_MODEL_ALIASES.get(normalized_input, normalized_input)
    return list(ACTIVE_COMMAND_PROFILES.get(normalized, ACTIVE_DEFAULT_COMMANDS))


def _device_type_for_model(model: str) -> str:
    """Return netmiko device_type for a configured model value."""
    normalized = _normalize_model(model)
    return ACTIVE_MODEL_ALIASES.get(normalized, normalized)


def run_capture_task(
    *,
    task_id: str,
    base: CaptureBase,
    hosts: list[dict[str, Any]],
    reserved_hosts: set[str],
) -> None:
    """Execute capture for queued hosts and persist task progress/results."""
    adapter = NetmikoAdapter()
    started = time.time()
    logger.info(
        "capture_task_started task_id=%s host_count=%d base=%s",
        task_id,
        len(hosts),
        base.value,
    )
    append_task_log(task_id, f"Task started at {started:.3f} for {len(hosts)} host(s)")
    update_task(task_id, status=CaptureTaskStatus.RUNNING, started_at=started)

    results: dict[str, Any] = {"hosts": [], "success_count": 0, "failure_count": 0}

    try:
        for host_info in hosts:
            hostname = host_info["host"]
            logger.info("capture_host_started task_id=%s host=%s", task_id, hostname)
            append_task_log(task_id, f"Starting host capture: {hostname}")
            if is_cancel_requested(task_id):
                append_task_log(task_id, "Cancellation requested. Stopping task.")
                update_task(
                    task_id,
                    status=CaptureTaskStatus.CANCELLED,
                    finished_at=time.time(),
                    result=results,
                )
                return

            commands = _commands_for_model(host_info["model"])
            try:
                outputs = adapter.capture_commands(
                    device_type=_device_type_for_model(host_info["model"]),
                    host=host_info["ip"],
                    username=host_info["username"],
                    port=int(host_info["port"]),
                    password=settings.device_password or "",
                    commands=commands,
                )
                files = []
                for command, output in outputs.items():
                    append_task_log(
                        task_id, f"Captured command '{command}' on {hostname}"
                    )
                    files.append(write_output(base.value, hostname, command, output))

                results["hosts"].append(
                    {
                        "host": hostname,
                        "status": "ok",
                        "commands": len(outputs),
                        "files": files,
                    }
                )
                results["success_count"] += 1
                logger.info(
                    "capture_host_completed task_id=%s host=%s", task_id, hostname
                )
                append_task_log(task_id, f"Host capture completed: {hostname}")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "capture_host_failed task_id=%s host=%s error=%s",
                    task_id,
                    hostname,
                    exc,
                )
                append_task_log(task_id, f"Host capture failed: {hostname} ({exc})")
                results["hosts"].append(
                    {"host": hostname, "status": "failed", "error": str(exc)}
                )
                results["failure_count"] += 1

        final_status = (
            CaptureTaskStatus.FAILED
            if results["failure_count"] > 0 and results["success_count"] == 0
            else CaptureTaskStatus.COMPLETED
        )
        update_task(
            task_id,
            status=final_status,
            finished_at=time.time(),
            result=results,
        )
        logger.info(
            "capture_task_finished task_id=%s status=%s", task_id, final_status.value
        )
        append_task_log(task_id, f"Task completed with status={final_status.value}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("capture_task_failed task_id=%s error=%s", task_id, exc)
        append_task_log(task_id, f"Task failed with unexpected error: {exc}")
        update_task(
            task_id,
            status=CaptureTaskStatus.FAILED,
            finished_at=time.time(),
            error=str(exc),
            result=results,
        )
    finally:
        release_hosts(reserved_hosts)
        logger.info("capture_task_lock_released task_id=%s", task_id)
        append_task_log(task_id, "Host locks released.")


def launch_capture_task(
    *,
    task_id: str,
    base: CaptureBase,
    hosts: list[dict[str, Any]],
    reserved_hosts: set[str],
) -> None:
    """
    Compatibility hook for API layer.

    Real execution is performed by the queue worker; this function only records
    that the task is ready in queued state.
    """
    append_task_log(
        task_id,
        f"Task queued for {len(hosts)} host(s) on base={base.value}",
    )
    _ = reserved_hosts
