"""Review queue routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")


@bp.get("")
def list_reviews():
    review_service = current_app.extensions["review_service"]
    reviews = review_service.list_open_reviews()
    return jsonify([item.to_dict() for item in reviews]), 200


@bp.post("/<review_id>/resolve")
def resolve_review(review_id: str):
    body = request.get_json(force=True, silent=True) or {}
    notes = str(body.get("resolution_notes", "")).strip()
    if not notes:
        return jsonify({"error": "missing field: resolution_notes"}), 400

    review_service = current_app.extensions["review_service"]
    try:
        item = review_service.resolve_review(review_id, notes)
    except KeyError:
        return jsonify({"error": "review item not found", "review_id": review_id}), 404
    return jsonify(item.to_dict()), 200
