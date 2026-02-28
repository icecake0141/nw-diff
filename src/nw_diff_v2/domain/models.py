"""Domain models for the v2 scaffold."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CaptureTaskStatus(str, Enum):
    """Capture task states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CaptureMode(str, Enum):
    """Capture request mode."""

    SINGLE = "single"
    BATCH = "batch"


class CaptureBase(str, Enum):
    """Capture target base."""

    ORIGIN = "origin"
    DEST = "dest"


class CaptureRequest(BaseModel):
    """Capture start request payload."""

    mode: CaptureMode
    base: CaptureBase
    hosts: list[str] = Field(default_factory=list)


class CaptureTaskResponse(BaseModel):
    """Capture start response payload."""

    task_id: str
    status: CaptureTaskStatus
    conflicts: list[str] = Field(default_factory=list)


class CaptureTaskDetail(BaseModel):
    """Detailed task view."""

    task_id: str
    status: CaptureTaskStatus
    mode: CaptureMode
    base: CaptureBase
    hosts: list[str] = Field(default_factory=list)
    requested_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_requested: bool = False
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None


class CaptureTaskSummary(BaseModel):
    """Summary row for task list endpoint."""

    task_id: str
    status: CaptureTaskStatus
    mode: CaptureMode
    base: CaptureBase
    hosts: list[str] = Field(default_factory=list)
    requested_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_requested: bool = False


class CompareFilesRequest(BaseModel):
    """Two-host comparison request for a single command."""

    host1: str
    host2: str
    base: CaptureBase
    command: str
    view: str = "sidebyside"


class HostRecord(BaseModel):
    """Validated host configuration row."""

    host: str
    ip: str
    username: str
    port: int
    model: str
