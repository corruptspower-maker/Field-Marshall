"""Flask app factory for the Phase 1 spine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from field_marshal.api.routes.reviews import bp as reviews_bp
from field_marshal.api.routes.system import bp as system_bp
from field_marshal.api.routes.tasks import bp as tasks_bp
from field_marshal.services.artifact_service import ArtifactService
from field_marshal.services.evidence_service import EvidenceService
from field_marshal.services.review_service import ReviewService
from field_marshal.services.task_service import TaskService
from field_marshal.store.db import Database
from field_marshal.store.repositories import (
    ArtifactRepository,
    EventRepository,
    ManifestRepository,
    ReviewRepository,
    TaskRepository,
)
from field_marshal.utils.config import load_app_config, require_config


def create_app(config_path: str | Path) -> Flask:
    config, root_dir = load_app_config(config_path)
    _validate_config(config)

    app = Flask(__name__)
    app.config["FM_CONFIG"] = config
    app.config["ROOT_DIR"] = str(root_dir)

    db_path = _resolve_rooted_path(root_dir, config["store"]["db_path"])
    manifests_dir = _resolve_rooted_path(root_dir, config["paths"]["manifests_dir"])

    db = Database(db_path)
    db.initialize()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    review_repo = ReviewRepository(db)
    artifact_repo = ArtifactRepository(db)
    manifest_repo = ManifestRepository(db)

    review_service = ReviewService(review_repo)
    task_service = TaskService(task_repo, event_repo, review_service)
    artifact_service = ArtifactService(artifact_repo, manifest_repo, manifests_dir)
    evidence_service = EvidenceService(event_repo)

    app.extensions["db"] = db
    app.extensions["task_service"] = task_service
    app.extensions["review_service"] = review_service
    app.extensions["artifact_service"] = artifact_service
    app.extensions["evidence_service"] = evidence_service

    app.register_blueprint(system_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(reviews_bp)

    return app


def _validate_config(config: dict[str, Any]) -> None:
    require_config(config, "api.host")
    require_config(config, "api.port")
    require_config(config, "store.db_path")
    require_config(config, "paths.manifests_dir")


def _resolve_rooted_path(root_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (root_dir / path).resolve()
