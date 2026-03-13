"""Persisted record models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    task_type: str
    phase: str
    status: str
    priority: int
    assigned_to: str | None
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None
    retry_count: int
    max_retries: int
    reason_code: str | None
    parent_task_id: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    parent_artifact_id: str | None
    task_id: str | None
    path: str
    checksum: str
    metadata_json: dict[str, Any]
    qa_status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventRecord:
    event_id: str
    task_id: str | None
    event_type: str
    message: str
    payload_json: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewItemRecord:
    review_id: str
    artifact_id: str | None
    task_id: str | None
    reason: str
    status: str
    resolution_notes: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ManifestRecord:
    id: str
    stage: str
    parent_id: str | None
    inputs_json: list[str]
    outputs_json: list[str]
    params_json: dict[str, Any]
    status: str
    qa_json: dict[str, Any]
    retry_count: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
