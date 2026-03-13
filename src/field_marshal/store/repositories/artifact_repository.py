"""Artifact persistence repository."""

from __future__ import annotations

import json

from field_marshal.store.db import Database
from field_marshal.store.models import ArtifactRecord


class ArtifactRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, artifact: ArtifactRecord) -> ArtifactRecord:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(
                    artifact_id, artifact_type, parent_artifact_id, task_id,
                    path, checksum, metadata_json, qa_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.artifact_type,
                    artifact.parent_artifact_id,
                    artifact.task_id,
                    artifact.path,
                    artifact.checksum,
                    json.dumps(artifact.metadata_json),
                    artifact.qa_status,
                    artifact.created_at,
                ),
            )
        return artifact

    def get(self, artifact_id: str) -> ArtifactRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_artifact(row)

    def list_for_task(self, task_id: str) -> list[ArtifactRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def update_qa_status(self, artifact_id: str, qa_status: str) -> ArtifactRecord:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE artifacts SET qa_status = ? WHERE artifact_id = ?",
                (qa_status, artifact_id),
            )
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Artifact not found: {artifact_id}")
        return _row_to_artifact(row)


def _row_to_artifact(row) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=row["artifact_id"],
        artifact_type=row["artifact_type"],
        parent_artifact_id=row["parent_artifact_id"],
        task_id=row["task_id"],
        path=row["path"],
        checksum=row["checksum"],
        metadata_json=json.loads(row["metadata_json"]),
        qa_status=row["qa_status"],
        created_at=row["created_at"],
    )
