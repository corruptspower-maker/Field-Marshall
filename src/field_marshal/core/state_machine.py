"""Canonical task status transitions."""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    AWAITING_DEPENDENCY = "awaiting_dependency"
    AWAITING_REVIEW = "awaiting_review"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    CANCELLED = "cancelled"


TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.QUEUED: {TaskStatus.CLAIMED, TaskStatus.CANCELLED},
    TaskStatus.CLAIMED: {TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.AWAITING_DEPENDENCY,
        TaskStatus.AWAITING_REVIEW,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED_RETRYABLE,
        TaskStatus.FAILED_TERMINAL,
        TaskStatus.CANCELLED,
    },
    TaskStatus.AWAITING_DEPENDENCY: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.AWAITING_REVIEW: {
        TaskStatus.QUEUED,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED_TERMINAL,
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED_RETRYABLE: {
        TaskStatus.QUEUED,
        TaskStatus.AWAITING_REVIEW,
        TaskStatus.FAILED_TERMINAL,
        TaskStatus.CANCELLED,
    },
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED_TERMINAL: set(),
    TaskStatus.CANCELLED: set(),
}

REASON_REQUIRED: set[TaskStatus] = {
    TaskStatus.FAILED_TERMINAL,
}


def can_transition(current: TaskStatus | str, target: TaskStatus | str) -> bool:
    """Return True if the transition is allowed."""
    source = TaskStatus(current)
    destination = TaskStatus(target)
    return destination in TRANSITIONS[source]


def enforce_transition(
    current: TaskStatus | str,
    target: TaskStatus | str,
    reason_code: str | None = None,
) -> None:
    """Raise ValueError if transition is invalid."""
    source = TaskStatus(current)
    destination = TaskStatus(target)
    if source == destination:
        return

    if destination in REASON_REQUIRED and not reason_code:
        raise ValueError(f"Transition to '{destination.value}' requires reason_code")

    if destination not in TRANSITIONS[source]:
        raise ValueError(
            f"Illegal task transition '{source.value}' -> '{destination.value}'"
        )
