"""Thin orchestration layer above task services."""

from __future__ import annotations

from field_marshal.core.contracts import TaskCreateContract
from field_marshal.core.state_machine import TaskStatus
from field_marshal.services.task_service import TaskService
from field_marshal.store.models import TaskRecord


class Orchestrator:
    """Dispatches bounded contracts without owning persistence."""

    def __init__(self, task_service: TaskService):
        self._task_service = task_service

    def submit_contract(self, contract: TaskCreateContract) -> TaskRecord:
        task = self._task_service.create_task(contract)
        return self._task_service.transition_task(
            task.task_id,
            TaskStatus.QUEUED,
            message="Task queued by orchestrator",
        )
