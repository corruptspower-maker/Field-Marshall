"""Event persistence repository."""

from __future__ import annotations

import json

from field_marshal.store.db import Database
from field_marshal.store.models import EventRecord


class EventRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, event: EventRecord) -> EventRecord:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO events(event_id, task_id, event_type, message, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.task_id,
                    event.event_type,
                    event.message,
                    json.dumps(event.payload_json),
                    event.created_at,
                ),
            )
        return event

    def list_for_task(self, task_id: str) -> list[EventRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]


def _row_to_event(row) -> EventRecord:
    return EventRecord(
        event_id=row["event_id"],
        task_id=row["task_id"],
        event_type=row["event_type"],
        message=row["message"],
        payload_json=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )
