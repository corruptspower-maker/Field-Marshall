"""Manifest persistence repository."""

from __future__ import annotations

import json

from field_marshal.store.db import Database
from field_marshal.store.models import ManifestRecord


class ManifestRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, manifest: ManifestRecord) -> ManifestRecord:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO manifests(
                    id, stage, parent_id, inputs_json, outputs_json, params_json,
                    status, qa_json, retry_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.id,
                    manifest.stage,
                    manifest.parent_id,
                    json.dumps(manifest.inputs_json),
                    json.dumps(manifest.outputs_json),
                    json.dumps(manifest.params_json),
                    manifest.status,
                    json.dumps(manifest.qa_json),
                    manifest.retry_count,
                    manifest.created_at,
                    manifest.updated_at,
                ),
            )
        return manifest

    def get(self, manifest_id: str) -> ManifestRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM manifests WHERE id = ?",
                (manifest_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_manifest(row)


def _row_to_manifest(row) -> ManifestRecord:
    return ManifestRecord(
        id=row["id"],
        stage=row["stage"],
        parent_id=row["parent_id"],
        inputs_json=json.loads(row["inputs_json"]),
        outputs_json=json.loads(row["outputs_json"]),
        params_json=json.loads(row["params_json"]),
        status=row["status"],
        qa_json=json.loads(row["qa_json"]),
        retry_count=row["retry_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
