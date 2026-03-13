from __future__ import annotations

import pytest

from field_marshal.core.state_machine import TaskStatus, can_transition, enforce_transition


def test_valid_running_to_succeeded_transition():
    assert can_transition(TaskStatus.RUNNING, TaskStatus.SUCCEEDED)
    enforce_transition(TaskStatus.RUNNING, TaskStatus.SUCCEEDED)


def test_invalid_pending_to_running_transition():
    assert not can_transition(TaskStatus.PENDING, TaskStatus.RUNNING)
    with pytest.raises(ValueError):
        enforce_transition(TaskStatus.PENDING, TaskStatus.RUNNING)


def test_failed_terminal_requires_reason_code():
    with pytest.raises(ValueError):
        enforce_transition(TaskStatus.RUNNING, TaskStatus.FAILED_TERMINAL)

    enforce_transition(
        TaskStatus.RUNNING,
        TaskStatus.FAILED_TERMINAL,
        reason_code="runtime_exception",
    )
