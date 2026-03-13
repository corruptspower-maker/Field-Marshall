from __future__ import annotations

from pathlib import Path

from field_marshal.core.contracts import FailureContract, TaskCreateContract
from field_marshal.core.state_machine import TaskStatus
from field_marshal.services.review_service import ReviewService
from field_marshal.services.task_service import TaskService
from field_marshal.store.db import Database
from field_marshal.store.repositories.event_repository import EventRepository
from field_marshal.store.repositories.review_repository import ReviewRepository
from field_marshal.store.repositories.task_repository import TaskRepository


def test_task_retry_escalates_to_review(tmp_path: Path):
    db_path = tmp_path / "registry.db"
    db = Database(db_path)
    db.initialize()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    review_repo = ReviewRepository(db)
    review_service = ReviewService(review_repo)
    task_service = TaskService(task_repo, event_repo, review_service)

    task = task_service.create_task(
        TaskCreateContract(
            task_type="detect.extract_frames",
            phase="detect",
            input_payload={"video_path": "assets/normalized_videos/demo.mp4"},
            max_retries=2,
        )
    )

    task = task_service.transition_task(task.task_id, TaskStatus.QUEUED)
    task = task_service.transition_task(task.task_id, TaskStatus.CLAIMED)
    task = task_service.transition_task(task.task_id, TaskStatus.RUNNING)

    failed_once = task_service.fail_task(
        FailureContract(
            task_id=task.task_id,
            reason_code="ffmpeg_timeout",
            message="FFmpeg timed out on first attempt",
        )
    )
    assert failed_once.status == TaskStatus.FAILED_RETRYABLE.value
    assert failed_once.retry_count == 1

    task = task_service.transition_task(task.task_id, TaskStatus.QUEUED)
    task = task_service.transition_task(task.task_id, TaskStatus.CLAIMED)
    task = task_service.transition_task(task.task_id, TaskStatus.RUNNING)

    failed_twice = task_service.fail_task(
        FailureContract(
            task_id=task.task_id,
            reason_code="ffmpeg_timeout",
            message="FFmpeg timed out on second attempt",
        )
    )
    assert failed_twice.status == TaskStatus.AWAITING_REVIEW.value
    assert failed_twice.retry_count == 2

    open_reviews = review_service.list_open_reviews()
    assert len(open_reviews) == 1
    assert open_reviews[0].task_id == task.task_id
