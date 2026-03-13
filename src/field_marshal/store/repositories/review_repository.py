"""Review queue persistence repository."""

from __future__ import annotations

from field_marshal.store.db import Database
from field_marshal.store.models import ReviewItemRecord


class ReviewRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, review_item: ReviewItemRecord) -> ReviewItemRecord:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO review_items(
                    review_id, artifact_id, task_id, reason, status, resolution_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_item.review_id,
                    review_item.artifact_id,
                    review_item.task_id,
                    review_item.reason,
                    review_item.status,
                    review_item.resolution_notes,
                    review_item.created_at,
                ),
            )
        return review_item

    def list_open(self) -> list[ReviewItemRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_items
                WHERE status IN ('open', 'awaiting_review')
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [_row_to_review(row) for row in rows]

    def resolve(self, review_id: str, notes: str) -> ReviewItemRecord:
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE review_items
                SET status = 'resolved', resolution_notes = ?
                WHERE review_id = ?
                """,
                (notes, review_id),
            )
            row = conn.execute(
                "SELECT * FROM review_items WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Review item not found: {review_id}")
        return _row_to_review(row)


def _row_to_review(row) -> ReviewItemRecord:
    return ReviewItemRecord(
        review_id=row["review_id"],
        artifact_id=row["artifact_id"],
        task_id=row["task_id"],
        reason=row["reason"],
        status=row["status"],
        resolution_notes=row["resolution_notes"],
        created_at=row["created_at"],
    )
