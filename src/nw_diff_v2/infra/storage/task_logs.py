"""Task log file helpers for v2 SSE stream."""

from __future__ import annotations

from pathlib import Path

from nw_diff_v2.config import settings


def task_log_dir() -> Path:
    path = Path(settings.artifact_root) / "task_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def task_log_path(task_id: str) -> Path:
    return task_log_dir() / f"{task_id}.log"


def append_task_log(task_id: str, line: str) -> None:
    path = task_log_path(task_id)
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{line}\n")
