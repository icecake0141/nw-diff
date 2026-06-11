"""Capture task log formatting helpers."""

from __future__ import annotations

from nw_diff_v2.infra.storage.task_logs import append_task_log

COMMAND_PREVIEW_LINES = 3
COMMAND_PREVIEW_LINE_CHARS = 200


def _sanitize_log_line(line: str) -> str:
    cleaned = "".join(
        ch if (ord(ch) >= 32 and ord(ch) != 127) else " " for ch in str(line)
    )
    return " ".join(cleaned.split())


def _command_preview_lines(
    output: str,
    *,
    preview_lines: int = COMMAND_PREVIEW_LINES,
    preview_line_chars: int = COMMAND_PREVIEW_LINE_CHARS,
) -> list[str]:
    lines = str(output).splitlines()[: max(0, preview_lines)]
    previews: list[str] = []
    for line in lines:
        safe = _sanitize_log_line(line)
        if len(safe) > preview_line_chars:
            safe = safe[: max(0, preview_line_chars - 3)] + "..."
        previews.append(safe)
    return previews


def append_command_preview_log(
    task_id: str,
    *,
    host: str,
    command: str,
    output: str,
) -> None:
    """Append bounded command output preview lines to the task log."""
    safe_host = _sanitize_log_line(host)
    safe_command = _sanitize_log_line(command)
    append_task_log(task_id, f"CMD_START host={safe_host} command={safe_command}")
    preview_lines = _command_preview_lines(output)
    if not preview_lines:
        append_task_log(
            task_id,
            f"CMD_PREVIEW host={safe_host} command={safe_command} line=1: <empty>",
        )
    for idx, line in enumerate(preview_lines, start=1):
        append_task_log(
            task_id,
            (
                "CMD_PREVIEW "
                f"host={safe_host} command={safe_command} line={idx}: {line}"
            ),
        )
    output_bytes = len(str(output).encode("utf-8", errors="replace"))
    append_task_log(
        task_id,
        f"CMD_END host={safe_host} command={safe_command} bytes={output_bytes}",
    )
