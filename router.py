"""
router.py — Field Marshal Flask router.

Serves both the REST API and the browser-based GUI dashboard on port 5000.
All shared state is protected by a single threading.Lock.
"""

import json
import queue
import threading
import time
import uuid
from collections import deque
import logging
import base64

from flask import Flask, Response, jsonify, render_template, request
import os
import requests

# ---------------------------------------------------------------------------
# Configuration / limits
# ---------------------------------------------------------------------------

# Maximum length (in characters) for base64-encoded screenshots attached to evidence.
# This limits in-memory usage even if a client sends a very large screenshot.
MAX_EVIDENCE_SCREENSHOT_B64_LEN = 1_000_000  # ~1 MB of base64 data

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Load configuration
try:
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        _config = json.load(f)
except (OSError, json.JSONDecodeError):
    _config = {}

_AGENT_CLAIM_TIMEOUT = _config.get("timeouts", {}).get("agent_claim_timeout", 60)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# task_id -> dict
_tasks: dict[str, dict] = {}

# task_id -> list[dict]  (agent → FM messages)
_task_messages: dict[str, list] = {}

# task_id -> dict | None  (FM reply waiting for agent)
_task_replies: dict[str, dict | None] = {}

# Evidence queue (deque so FM can drain it quickly)
_evidence_queue: deque = deque()

# SSE event queue fed by field_marshal.py supervision watcher
_SSE_QUEUE_MAXSIZE = 1024
_sse_queue: queue.Queue = queue.Queue(maxsize=_SSE_QUEUE_MAXSIZE)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _task_or_404(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if task is None:
        return None, jsonify({"error": "task not found", "task_id": task_id}), 404
    return task, None, None


def _push_sse(event_type: str, data: dict):
    """Push an event into the SSE queue (non-blocking).

    The queue is bounded; if it is full, drop the oldest event and log a warning.
    """
    event = {"type": event_type, "data": data, "ts": time.time()}
    try:
        _sse_queue.put_nowait(event)
    except queue.Full:
        # Queue is full: drop the oldest event to make room for the newest one.
        try:
            _sse_queue.get_nowait()
        except queue.Empty:
            # If the queue was reported full but is now empty, just log and continue.
            logger.warning("SSE queue reported full but was empty when draining; dropping event %s", event_type)
        try:
            _sse_queue.put_nowait(event)
        except queue.Full:
            # If we still can't enqueue, drop this event and log.
            logger.warning("SSE queue is full; dropping event %s", event_type)


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------

_SHARED_TOKEN = os.environ.get("FM_SHARED_TOKEN")


@app.before_request
def _enforce_task_auth():
    """
    Protect task-related endpoints so they cannot be abused if the router
    is exposed beyond localhost.

    Rules:
      - Only specific sensitive paths are protected:
          * /task/...
          * /tasks...
          * /evidence...
          * /chat...
          * /stream...
      - Localhost (127.0.0.1, ::1) access is always allowed.
      - For non-localhost access:
          * If FM_SHARED_TOKEN is unset, deny access.
          * If FM_SHARED_TOKEN is set, require it via header or query param.
    """
    path = request.path or ""
    protected_prefixes = ("/task/", "/tasks", "/evidence", "/chat", "/stream")
    if not any(path.startswith(p) for p in protected_prefixes):
        return None

    remote = request.remote_addr or ""
    if remote in ("127.0.0.1", "::1"):
        return None

    if not _SHARED_TOKEN:
        return jsonify({"error": "task API is restricted to localhost"}), 403

    token = request.headers.get("X-Field-Marshal-Token") or request.args.get("token")
    if token != _SHARED_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    return None


# ---------------------------------------------------------------------------
# Task lifecycle endpoints
# ---------------------------------------------------------------------------

@app.route("/task/submit", methods=["POST"])
def task_submit():
    body = request.get_json(force=True, silent=True) or {}
    target = body.get("target", "terminal")
    payload = body.get("payload", "")
    task_id = str(uuid.uuid4())
    now = time.time()
    task = {
        "task_id": task_id,
        "target": target,
        "payload": payload,
        "status": "pending",
        "created_at": now,
        "claimed_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
        "claimed_by": None,
    }
    with _lock:
        _tasks[task_id] = task
        _task_messages[task_id] = []
        _task_replies[task_id] = None
    _push_sse("dispatch", {"task_id": task_id, "target": target, "payload": str(payload)[:120]})
    return jsonify({"task_id": task_id, "status": "pending"}), 201


@app.route("/task/claim", methods=["POST"])
def task_claim():
    body = request.get_json(force=True, silent=True) or {}
    agent_id = body.get("agent_id", "unknown")
    target = body.get("target", "terminal")
    now = time.time()
    claim_timeout = _AGENT_CLAIM_TIMEOUT

    with _lock:
        for task in _tasks.values():
            if task["status"] == "pending" and task["target"] == target:
                task["status"] = "claimed"
                task["claimed_at"] = now
                task["claimed_by"] = agent_id
                return jsonify(task), 200
            # Re-claim stale tasks
            if (
                task["status"] == "claimed"
                and task["target"] == target
                and task["claimed_at"] is not None
                and (now - task["claimed_at"]) > claim_timeout
            ):
                task["status"] = "claimed"
                task["claimed_at"] = now
                task["claimed_by"] = agent_id
                return jsonify(task), 200

    return jsonify({"task_id": None}), 200


@app.route("/task/<task_id>/complete", methods=["POST"])
def task_complete(task_id: str):
    task, err_resp, code = _task_or_404(task_id)
    if err_resp:
        return err_resp, code
    body = request.get_json(force=True, silent=True) or {}
    with _lock:
        task["status"] = "completed"
        task["completed_at"] = time.time()
        task["result"] = body.get("result")
        task["error"] = body.get("error")
    _push_sse(
        "status",
        {
            "task_id": task_id,
            "status": "completed",
            "target": task["target"],
            "has_error": bool(task["error"]),
        },
    )
    return jsonify({"task_id": task_id, "status": "completed"}), 200


@app.route("/task/<task_id>/result", methods=["GET"])
def task_result(task_id: str):
    task, err_resp, code = _task_or_404(task_id)
    if err_resp:
        return err_resp, code
    return jsonify(task), 200


@app.route("/tasks", methods=["GET"])
def tasks_list():
    with _lock:
        snapshot = list(_tasks.values())
    return jsonify(snapshot), 200


# ---------------------------------------------------------------------------
# Bidirectional messaging (agent ↔ Field Marshal)
# ---------------------------------------------------------------------------

@app.route("/task/<task_id>/message", methods=["POST"])
def task_message(task_id: str):
    """Agent → Field Marshal mid-task message."""
    task, err_resp, code = _task_or_404(task_id)
    if err_resp:
        return err_resp, code
    body = request.get_json(force=True, silent=True) or {}
    msg = {
        "task_id": task_id,
        "source": body.get("source", "agent"),
        "text": body.get("text", ""),
        "ts": time.time(),
    }
    with _lock:
        _task_messages[task_id].append(msg)
    return jsonify({"status": "received"}), 200


@app.route("/task/<task_id>/messages", methods=["GET"])
def task_messages(task_id: str):
    """Field Marshal polls for agent messages."""
    _, err_resp, code = _task_or_404(task_id)
    if err_resp:
        return err_resp, code
    with _lock:
        msgs = list(_task_messages.get(task_id, []))
        _task_messages[task_id] = []
    return jsonify(msgs), 200


@app.route("/task/<task_id>/reply", methods=["POST"])
def task_reply_post(task_id: str):
    """Field Marshal → agent reply."""
    _, err_resp, code = _task_or_404(task_id)
    if err_resp:
        return err_resp, code
    body = request.get_json(force=True, silent=True) or {}
    with _lock:
        _task_replies[task_id] = {"text": body.get("text", ""), "ts": time.time()}
    return jsonify({"status": "queued"}), 200


@app.route("/task/<task_id>/reply", methods=["GET"])
def task_reply_get(task_id: str):
    """Agent polls for FM reply."""
    _, err_resp, code = _task_or_404(task_id)
    if err_resp:
        return err_resp, code
    with _lock:
        reply = _task_replies.get(task_id)
        _task_replies[task_id] = None
    if reply:
        return jsonify(reply), 200
    return jsonify({"text": None}), 200


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@app.route("/evidence", methods=["POST"])
def evidence_submit():
    packet = request.get_json(force=True, silent=True) or {}

    # Basic schema and size validation to prevent abuse (e.g., huge screenshots).
    if not isinstance(packet, dict):
        return jsonify({"error": "Invalid JSON payload; expected an object"}), 400

    task_id = packet.get("task_id")
    source_agent = packet.get("source_agent")
    severity = packet.get("severity", "info")
    caption = packet.get("caption", "")
    screenshot_b64 = packet.get("screenshot_b64")

    # Required fields must be non-empty strings.
    if not isinstance(task_id, str) or not task_id:
        return jsonify({"error": "Field 'task_id' is required and must be a non-empty string"}), 400
    if not isinstance(source_agent, str) or not source_agent:
        return jsonify({"error": "Field 'source_agent' is required and must be a non-empty string"}), 400

    # Optional fields: normalize types and enforce size constraints.
    if not isinstance(severity, str):
        return jsonify({"error": "Field 'severity' must be a string"}), 400

    if not isinstance(caption, str):
        return jsonify({"error": "Field 'caption' must be a string if provided"}), 400
    # Truncate caption to 200 characters (existing behavior).
    caption = caption[:200]
    packet["caption"] = caption

    if screenshot_b64 is not None:
        if not isinstance(screenshot_b64, str):
            return jsonify({"error": "Field 'screenshot_b64' must be a base64 string if provided"}), 400
        if len(screenshot_b64) > MAX_EVIDENCE_SCREENSHOT_B64_LEN:
            return (
                jsonify(
                    {
                        "error": "Field 'screenshot_b64' is too large",
                        "max_len": MAX_EVIDENCE_SCREENSHOT_B64_LEN,
                    }
                ),
                413,
            )
        # Validate that screenshot_b64 contains valid base64 data to prevent
        # downstream failures when constructing data:image URLs.
        try:
            # validate=True enforces that the string contains only valid base64 characters.
            base64.b64decode(screenshot_b64, validate=True)
        except Exception:
            return (
                jsonify(
                    {
                        "error": "Field 'screenshot_b64' must be valid base64-encoded data",
                    }
                ),
                400,
            )

    packet.setdefault("timestamp", time.time())
    with _lock:
        _evidence_queue.append(packet)
    _push_sse(
        "evidence",
        {
            "task_id": task_id,
            "source_agent": source_agent,
            "severity": severity,
            "caption": caption,
            "has_screenshot": bool(screenshot_b64),
        },
    )
    return jsonify({"status": "received"}), 200


@app.route("/evidence/pending", methods=["GET"])
def evidence_pending():
    packets = []
    with _lock:
        while _evidence_queue:
            packets.append(_evidence_queue.popleft())
    return jsonify(packets), 200


# ---------------------------------------------------------------------------
# GUI — dashboard + chat
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Human sends a message to the Bondsman. Returns the response as JSON."""
    body = request.get_json(force=True, silent=True) or {}
    user_input = body.get("message", "").strip()
    if not user_input:
        return jsonify({"error": "empty message"}), 400

    # Forward the chat message to the external Field Marshal brain service.
    # The target URL can be overridden via FIELD_MARSHAL_CHAT_URL.
    brain_url = os.environ.get("FIELD_MARSHAL_CHAT_URL", "http://127.0.0.1:8001/chat")
    try:
        resp = requests.post(brain_url, json={"message": user_input}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Expect the external service to return {"response": "..."}; fall back gracefully.
        response_text = data.get("response") if isinstance(data, dict) else str(data)
        if not response_text:
            response_text = str(data)
    except Exception as exc:  # pragma: no cover
        response_text = f"[Field Marshal unavailable: {exc}]"

    _push_sse("status", {"event": "chat_response", "preview": response_text[:80]})
    return jsonify({"response": response_text}), 200


# ---------------------------------------------------------------------------
# SSE live feed
# ---------------------------------------------------------------------------

@app.route("/stream")
def stream():
    """Server-Sent Events endpoint for the live dashboard feed."""

    def event_generator():
        # Send a heartbeat immediately so the browser knows it's alive
        yield "data: {\"type\": \"heartbeat\"}\n\n"
        while True:
            try:
                event = _sse_queue.get(timeout=15)
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                yield "data: {\"type\": \"heartbeat\"}\n\n"

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    with _lock:
        total = len(_tasks)
        active = sum(1 for t in _tasks.values() if t["status"] in ("pending", "claimed"))
        pending_evidence = len(_evidence_queue)
    return jsonify(
        {
            "status": "ok",
            "tasks_total": total,
            "tasks_active": active,
            "evidence_pending": pending_evidence,
            "sse_queue_size": _sse_queue.qsize(),
        }
    ), 200


# ---------------------------------------------------------------------------
# Expose SSE push for field_marshal.py
# ---------------------------------------------------------------------------

def push_sse_event(event_type: str, data: dict):
    """Public API so field_marshal.py can push events without importing _push_sse."""
    _push_sse(event_type, data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)
    router_cfg = cfg.get("router", {})
    app.run(
        host=router_cfg.get("host", "127.0.0.1"),
        port=router_cfg.get("port", 5000),
        debug=router_cfg.get("debug", False),
        threaded=True,
    )
