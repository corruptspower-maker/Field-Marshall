"""Evidence and event service."""

from __future__ import annotations

import uuid
from typing import Any

from field_marshal.store.models import EventRecord, utc_now
from field_marshal.store.repositories.event_repository import EventRepository


class EvidenceService:
    """Stores evidence as typed event records."""

    def __init__(self, event_repo: EventRepository):
        self._event_repo = event_repo

    def record_event(
        self,
        *,
        task_id: str | None,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> EventRecord:
        event = EventRecord(
            event_id=str(uuid.uuid4()),
            task_id=task_id,
            event_type=event_type,
            message=message,
            payload_json=payload or {},
            created_at=utc_now(),
        )
        return self._event_repo.create(event)

    def list_task_events(self, task_id: str) -> list[EventRecord]:
        return self._event_repo.list_for_task(task_id)
