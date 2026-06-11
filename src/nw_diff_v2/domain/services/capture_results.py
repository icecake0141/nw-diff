"""Typed capture task result payloads."""

from __future__ import annotations

from typing import TypedDict


class CaptureHostResult(TypedDict, total=False):
    """One host entry in a capture task result."""

    host: str
    status: str
    commands: int
    files: list[str]
    error: str


class CaptureTaskResult(TypedDict):
    """Capture task result persisted in the task repository."""

    hosts: list[CaptureHostResult]
    success_count: int
    failure_count: int
