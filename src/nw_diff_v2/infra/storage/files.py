"""Artifact storage helpers for v2 capture outputs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from nw_diff_v2.config import settings

_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]")
ARTIFACT_SEP = "~"


def _sanitize(value: str) -> str:
    return _SAFE_RE.sub("_", value)


def artifact_path(base: str, host: str, command: str) -> Path:
    """Build normalized artifact path for a command output."""
    safe_host = _sanitize(host)
    safe_cmd = _sanitize(command.replace(" ", "_"))
    root = Path(settings.artifact_root) / base
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe_host}{ARTIFACT_SEP}{safe_cmd}.txt"


def write_output(base: str, host: str, command: str, output: str) -> str:
    """Write command output and return written path."""
    path = artifact_path(base, host, command)
    path.write_text(output, encoding="utf-8")
    return str(path)


def list_command_keys(base: str, host: str) -> set[str]:
    """List stored command keys for the target host and base."""
    safe_host = _sanitize(host)
    root = Path(settings.artifact_root) / base
    if not root.exists():
        return set()
    result: set[str] = set()
    prefix = f"{safe_host}{ARTIFACT_SEP}"
    for path in root.glob(f"{prefix}*.txt"):
        stem = path.stem
        if not stem.startswith(prefix):
            continue
        result.add(stem[len(prefix) :])
    return result


def read_output_by_key(
    base: str, host: str, command_key: str
) -> tuple[str, Optional[str]]:
    """Read output by stored command key and return (status, content)."""
    safe_host = _sanitize(host)
    safe_key = _sanitize(command_key)
    path = Path(settings.artifact_root) / base / f"{safe_host}{ARTIFACT_SEP}{safe_key}.txt"
    if not path.exists():
        return "not_found", None
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return "error", None

    if content.startswith("[UNAVAILABLE:"):
        marker = content.split("[UNAVAILABLE:", 1)[1].split("]", 1)[0].strip()
        return (marker or "unavailable"), content
    return "available", content


def command_label_from_key(command_key: str) -> str:
    """Best-effort display label for command key."""
    return command_key.replace("_", " ")


def artifact_path_by_key(base: str, host: str, command_key: str) -> Path:
    """Build artifact path from already-normalized command key."""
    safe_host = _sanitize(host)
    safe_key = _sanitize(command_key)
    root = Path(settings.artifact_root) / base
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe_host}{ARTIFACT_SEP}{safe_key}.txt"


def list_artifact_files(base: str, host: str) -> list[Path]:
    """List artifact files for a host and base using strict host boundary."""
    safe_host = _sanitize(host)
    root = Path(settings.artifact_root) / base
    if not root.exists():
        return []
    prefix = f"{safe_host}{ARTIFACT_SEP}"
    return sorted(path for path in root.glob(f"{prefix}*.txt") if path.stem.startswith(prefix))
