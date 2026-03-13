"""System-level routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify


bp = Blueprint("system", __name__)


@bp.get("/health")
def health():
    db = current_app.extensions["db"]
    return (
        jsonify(
            {
                "status": "ok",
                "db_path": str(db.db_path),
                "service": "field-marshal-factory",
            }
        ),
        200,
    )
