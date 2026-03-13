"""Core task and manifest contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TaskCreateContract:
    """Bounded contract for creating a new task."""

    task_type: str
    phase: str
    input_payload: dict[str, Any]
    priority: int = 50
    assigned_to: str | None = None
    max_retries: int = 3
    parent_task_id: str | None = None


@dataclass(slots=True)
class TaskTransitionContract:
    """Bounded contract for transitioning a task state."""

    task_id: str
    to_status: str
    reason_code: str | None = None
    message: str = ""


@dataclass(slots=True)
class FailureContract:
    """Bounded contract for a retryable or terminal failure."""

    task_id: str
    reason_code: str
    message: str


@dataclass(slots=True)
class ManifestContract:
    """Canonical stage manifest shape."""

    id: str
    stage: str
    inputs: list[str]
    outputs: list[str]
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "succeeded"
    qa: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    parent_id: str | None = None
