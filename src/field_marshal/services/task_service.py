"""Task orchestration service."""

from __future__ import annotations

import uuid

from field_marshal.core.contracts import FailureContract, TaskCreateContract
from field_marshal.core.state_machine import TaskStatus, enforce_transition
from field_marshal.services.review_service import ReviewService
from field_marshal.store.models import EventRecord, TaskRecord, utc_now
from field_marshal.store.repositories.event_repository import EventRepository
from field_marshal.store.repositories.task_repository import TaskRepository


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        event_repo: EventRepository,
        review_service: ReviewService,
    ):
        self._task_repo = task_repo
        self._event_repo = event_repo
        self._review_service = review_service

    def create_task(self, contract: TaskCreateContract) -> TaskRecord:
        now = utc_now()
        task = TaskRecord(
            task_id=str(uuid.uuid4()),
            task_type=contract.task_type,
            phase=contract.phase,
            status=TaskStatus.PENDING.value,
            priority=contract.priority,
            assigned_to=contract.assigned_to,
            input_payload=contract.input_payload,
            output_payload=None,
            retry_count=0,
            max_retries=contract.max_retries,
            reason_code=None,
            parent_task_id=contract.parent_task_id,
            created_at=now,
            updated_at=now,
        )
        created = self._task_repo.create(task)
        self._append_event(
            task_id=created.task_id,
            event_type="task_created",
            message="Task created",
            payload={"status": created.status, "task_type": created.task_type},
        )
        return created

    def get_task(self, task_id: str) -> TaskRecord:
        task = self._task_repo.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        return task

    def list_tasks(self, status: str | None = None, limit: int = 200) -> list[TaskRecord]:
        return self._task_repo.list(status=status, limit=limit)

    def transition_task(
        self,
        task_id: str,
        to_status: TaskStatus | str,
        *,
        reason_code: str | None = None,
        message: str = "",
    ) -> TaskRecord:
        current = self.get_task(task_id)
        target = TaskStatus(to_status)
        enforce_transition(current.status, target, reason_code=reason_code)

        updated = self._task_repo.update_status(
            task_id,
            target.value,
            reason_code=reason_code,
        )
        self._append_event(
            task_id=task_id,
            event_type="task_transition",
            message=message or "Task state transition",
            payload={
                "from_status": current.status,
                "to_status": updated.status,
                "reason_code": reason_code,
            },
        )
        return updated

    def complete_task(
        self,
        task_id: str,
        output_payload: dict,
    ) -> TaskRecord:
        current = self.get_task(task_id)
        enforce_transition(current.status, TaskStatus.SUCCEEDED)
        self._task_repo.update_output(task_id, output_payload)
        updated = self._task_repo.update_status(task_id, TaskStatus.SUCCEEDED.value)
        self._append_event(
            task_id=task_id,
            event_type="task_completed",
            message="Task completed successfully",
            payload={"output_keys": sorted(output_payload.keys())},
        )
        return updated

    def fail_task(self, contract: FailureContract) -> TaskRecord:
        current = self.get_task(contract.task_id)
        next_retry_count = current.retry_count + 1
        next_status = (
            TaskStatus.AWAITING_REVIEW
            if next_retry_count >= current.max_retries
            else TaskStatus.FAILED_RETRYABLE
        )
        enforce_transition(current.status, next_status, reason_code=contract.reason_code)

        updated = self._task_repo.set_failure(
            contract.task_id,
            status=next_status.value,
            reason_code=contract.reason_code,
            retry_count=next_retry_count,
        )
        self._append_event(
            task_id=contract.task_id,
            event_type="task_failed",
            message=contract.message,
            payload={
                "reason_code": contract.reason_code,
                "retry_count": next_retry_count,
                "status": next_status.value,
            },
        )

        if next_status is TaskStatus.AWAITING_REVIEW:
            self._review_service.create_task_review(
                task_id=contract.task_id,
                reason=f"Retry budget exhausted: {contract.reason_code}",
            )

        return updated

    def _append_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str,
        payload: dict,
    ) -> None:
        self._event_repo.create(
            EventRecord(
                event_id=str(uuid.uuid4()),
                task_id=task_id,
                event_type=event_type,
                message=message,
                payload_json=payload,
                created_at=utc_now(),
            )
        )
