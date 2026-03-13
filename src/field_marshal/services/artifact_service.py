"""Artifact and manifest service."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from field_marshal.core.contracts import ManifestContract
from field_marshal.store.models import ArtifactRecord, ManifestRecord, utc_now
from field_marshal.store.repositories.artifact_repository import ArtifactRepository
from field_marshal.store.repositories.manifest_repository import ManifestRepository


class ArtifactService:
    def __init__(
        self,
        artifact_repo: ArtifactRepository,
        manifest_repo: ManifestRepository,
        manifests_dir: str | Path,
    ):
        self._artifact_repo = artifact_repo
        self._manifest_repo = manifest_repo
        self._manifests_dir = Path(manifests_dir)
        self._manifests_dir.mkdir(parents=True, exist_ok=True)

    def register_artifact(
        self,
        *,
        artifact_type: str,
        path: str | Path,
        task_id: str | None,
        metadata: dict[str, Any] | None = None,
        parent_artifact_id: str | None = None,
        qa_status: str = "pending",
    ) -> ArtifactRecord:
        file_path = Path(path)
        checksum = _sha256(file_path)
        artifact = ArtifactRecord(
            artifact_id=str(uuid.uuid4()),
            artifact_type=artifact_type,
            parent_artifact_id=parent_artifact_id,
            task_id=task_id,
            path=str(file_path),
            checksum=checksum,
            metadata_json=metadata or {},
            qa_status=qa_status,
            created_at=utc_now(),
        )
        return self._artifact_repo.create(artifact)

    def write_manifest(self, contract: ManifestContract) -> ManifestRecord:
        now = utc_now()
        manifest_payload = {
            "id": contract.id,
            "stage": contract.stage,
            "parent_id": contract.parent_id,
            "inputs": contract.inputs,
            "outputs": contract.outputs,
            "params": contract.params,
            "status": contract.status,
            "qa": contract.qa,
            "retry_count": contract.retry_count,
            "timestamps": {"created_at": now, "updated_at": now},
        }

        manifest_path = self._manifests_dir / f"{contract.id}.json"
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

        manifest_record = ManifestRecord(
            id=contract.id,
            stage=contract.stage,
            parent_id=contract.parent_id,
            inputs_json=contract.inputs,
            outputs_json=contract.outputs,
            params_json=contract.params,
            status=contract.status,
            qa_json=contract.qa,
            retry_count=contract.retry_count,
            created_at=now,
            updated_at=now,
        )
        return self._manifest_repo.create(manifest_record)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
