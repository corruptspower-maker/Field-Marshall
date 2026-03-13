"""Review queue service."""

from __future__ import annotations

import uuid

from field_marshal.store.models import ReviewItemRecord, utc_now
from field_marshal.store.repositories.review_repository import ReviewRepository


class ReviewService:
    def __init__(self, review_repo: ReviewRepository):
        self._review_repo = review_repo

    def create_task_review(
        self,
        *,
        task_id: str,
        reason: str,
        artifact_id: str | None = None,
    ) -> ReviewItemRecord:
        review_item = ReviewItemRecord(
            review_id=str(uuid.uuid4()),
            artifact_id=artifact_id,
            task_id=task_id,
            reason=reason,
            status="awaiting_review",
            resolution_notes=None,
            created_at=utc_now(),
        )
        return self._review_repo.create(review_item)

    def list_open_reviews(self) -> list[ReviewItemRecord]:
        return self._review_repo.list_open()

    def resolve_review(self, review_id: str, notes: str) -> ReviewItemRecord:
        return self._review_repo.resolve(review_id, notes)
