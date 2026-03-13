"""Task persistence repository."""

from __future__ import annotations

import json

from field_marshal.store.db import Database
from field_marshal.store.models import TaskRecord, utc_now


class TaskRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, task: TaskRecord) -> TaskRecord:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, task_type, phase, status, priority, assigned_to,
                    input_payload, output_payload, retry_count, max_retries,
                    reason_code, parent_task_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.task_type,
                    task.phase,
                    task.status,
                    task.priority,
                    task.assigned_to,
                    json.dumps(task.input_payload),
                    json.dumps(task.output_payload) if task.output_payload else None,
                    task.retry_count,
                    task.max_retries,
                    task.reason_code,
                    task.parent_task_id,
                    task.created_at,
                    task.updated_at,
                ),
            )
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    def list(self, status: str | None = None, limit: int = 200) -> list[TaskRecord]:
        query = "SELECT * FROM tasks"
        params: tuple[object, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC LIMIT ?"
        params = (*params, limit)

        with self._db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_task(row) for row in rows]

    def update_status(
        self,
        task_id: str,
        status: str,
        *,
        reason_code: str | None = None,
    ) -> TaskRecord:
        updated_at = utc_now()
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, reason_code = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status, reason_code, updated_at, task_id),
            )
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Task not found: {task_id}")
        return _row_to_task(row)

    def update_output(self, task_id: str, output_payload: dict) -> TaskRecord:
        updated_at = utc_now()
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET output_payload = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (json.dumps(output_payload), updated_at, task_id),
            )
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Task not found: {task_id}")
        return _row_to_task(row)

    def set_failure(
        self,
        task_id: str,
        *,
        status: str,
        reason_code: str,
        retry_count: int,
    ) -> TaskRecord:
        updated_at = utc_now()
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, reason_code = ?, retry_count = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status, reason_code, retry_count, updated_at, task_id),
            )
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Task not found: {task_id}")
        return _row_to_task(row)


def _row_to_task(row) -> TaskRecord:
    output_payload = row["output_payload"]
    return TaskRecord(
        task_id=row["task_id"],
        task_type=row["task_type"],
        phase=row["phase"],
        status=row["status"],
        priority=row["priority"],
        assigned_to=row["assigned_to"],
        input_payload=json.loads(row["input_payload"]),
        output_payload=json.loads(output_payload) if output_payload else None,
        retry_count=row["retry_count"],
        max_retries=row["max_retries"],
        reason_code=row["reason_code"],
        parent_task_id=row["parent_task_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
