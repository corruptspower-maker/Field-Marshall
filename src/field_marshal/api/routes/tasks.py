"""Task routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from field_marshal.core.contracts import FailureContract, TaskCreateContract
from field_marshal.core.state_machine import TaskStatus


bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@bp.post("")
def create_task():
    body = request.get_json(force=True, silent=True) or {}
    try:
        contract = TaskCreateContract(
            task_type=str(body["task_type"]),
            phase=str(body["phase"]),
            input_payload=body.get("input_payload", {}),
            priority=int(body.get("priority", 50)),
            assigned_to=body.get("assigned_to"),
            max_retries=int(body.get("max_retries", 3)),
            parent_task_id=body.get("parent_task_id"),
        )
    except KeyError as exc:
        return jsonify({"error": f"missing field: {exc}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"invalid payload: {exc}"}), 400

    task_service = current_app.extensions["task_service"]
    task = task_service.create_task(contract)
    return jsonify(task.to_dict()), 201


@bp.get("")
def list_tasks():
    status = request.args.get("status")
    limit = int(request.args.get("limit", "200"))
    task_service = current_app.extensions["task_service"]
    tasks = task_service.list_tasks(status=status, limit=limit)
    return jsonify([task.to_dict() for task in tasks]), 200


@bp.get("/<task_id>")
def get_task(task_id: str):
    task_service = current_app.extensions["task_service"]
    try:
        task = task_service.get_task(task_id)
    except KeyError:
        return jsonify({"error": "task not found", "task_id": task_id}), 404
    return jsonify(task.to_dict()), 200


@bp.post("/<task_id>/transition")
def transition_task(task_id: str):
    body = request.get_json(force=True, silent=True) or {}
    raw_status = body.get("to_status")
    if not raw_status:
        return jsonify({"error": "missing field: to_status"}), 400

    task_service = current_app.extensions["task_service"]
    try:
        task = task_service.transition_task(
            task_id,
            TaskStatus(raw_status),
            reason_code=body.get("reason_code"),
            message=str(body.get("message", "")),
        )
    except KeyError:
        return jsonify({"error": "task not found", "task_id": task_id}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(task.to_dict()), 200


@bp.post("/<task_id>/complete")
def complete_task(task_id: str):
    body = request.get_json(force=True, silent=True) or {}
    output_payload = body.get("output_payload", {})
    if not isinstance(output_payload, dict):
        return jsonify({"error": "output_payload must be an object"}), 400

    task_service = current_app.extensions["task_service"]
    try:
        task = task_service.complete_task(task_id, output_payload)
    except KeyError:
        return jsonify({"error": "task not found", "task_id": task_id}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(task.to_dict()), 200


@bp.post("/<task_id>/fail")
def fail_task(task_id: str):
    body = request.get_json(force=True, silent=True) or {}
    reason_code = str(body.get("reason_code", "")).strip()
    message = str(body.get("message", "Task failed")).strip()
    if not reason_code:
        return jsonify({"error": "missing field: reason_code"}), 400

    task_service = current_app.extensions["task_service"]
    try:
        task = task_service.fail_task(
            FailureContract(task_id=task_id, reason_code=reason_code, message=message)
        )
    except KeyError:
        return jsonify({"error": "task not found", "task_id": task_id}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(task.to_dict()), 200
