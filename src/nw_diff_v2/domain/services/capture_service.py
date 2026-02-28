"""Capture task execution service for v2."""

from __future__ import annotations

import time
from typing import Any
import logging

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureBase, CaptureTaskStatus
from nw_diff_v2.domain.services.lock_service import release_hosts
from nw_diff_v2.infra.adapters.netmiko_adapter import NetmikoAdapter
from nw_diff_v2.infra.repositories.task_repo import is_cancel_requested, update_task
from nw_diff_v2.infra.storage.files import write_output
from nw_diff_v2.infra.storage.task_logs import append_task_log

COMMAND_PROFILES: dict[str, tuple[str, ...]] = {
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
}
DEFAULT_COMMANDS = ("show version",)
logger = logging.getLogger("nw-diff-v2")


def _commands_for_model(model: str) -> list[str]:
    return list(COMMAND_PROFILES.get(model.lower(), DEFAULT_COMMANDS))


def run_capture_task(
    *,
    task_id: str,
    base: CaptureBase,
    hosts: list[dict[str, Any]],
    reserved_hosts: set[str],
) -> None:
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
                    device_type=host_info["model"],
                    host=host_info["ip"],
                    username=host_info["username"],
                    port=int(host_info["port"]),
                    password=settings.device_password or "",
                    commands=commands,
                )
                files = []
                for command, output in outputs.items():
                    append_task_log(task_id, f"Captured command '{command}' on {hostname}")
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
                logger.info("capture_host_completed task_id=%s host=%s", task_id, hostname)
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
        logger.info("capture_task_finished task_id=%s status=%s", task_id, final_status.value)
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
