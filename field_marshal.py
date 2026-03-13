"""
field_marshal.py — Lord + Bondsman brain and supervision loop.

Responsibilities:
- Load personas from personas/bondsman.md and personas/lord.md
- Expose handle_chat() for the GUI /chat endpoint
- Run background supervision watcher (evidence + mid-task messages)
- Lord/Bondsman multi-round dialectic
- Startup self-test
"""

import json
import os
import re
import threading
import time
from typing import Any, Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_BASE_DIR, "config.json")) as _f:
    _CFG = json.load(_f)

_LMS = _CFG["lmstudio"]
_BASE_URL = _LMS["base_url"]
_API_TOKEN = _LMS["api_token"]
_BONDSMAN_MODEL = _LMS["llm_model"]
_LORD_MODEL = _LMS["lord_model"]
_ROUTER_URL = f"http://{_CFG['router']['host']}:{_CFG['router']['port']}"

# ---------------------------------------------------------------------------
# Persona loading
# ---------------------------------------------------------------------------

def _load_persona(filename: str, fallback: str) -> str:
    path = os.path.join(_BASE_DIR, "personas", filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return fallback


_BONDSMAN_SYSTEM = _load_persona(
    "bondsman.md",
    "You are the Bondsman — the campaign mind of the Field Marshal system. "
    "Command agents via [DISPATCH:target] syntax. Defend interpretations to the Lord.",
)

_LORD_SYSTEM = _load_persona(
    "lord.md",
    "You are the Lord — the adversarial interrogator of the Field Marshal system. "
    "Challenge the Bondsman's evidence interpretations. Say [RESOLVED] when satisfied.",
)

# ---------------------------------------------------------------------------
# RAG (optional ChromaDB)
# ---------------------------------------------------------------------------

_rag_collection = None

def _init_rag():
    global _rag_collection
    try:
        import chromadb  # type: ignore
        client = chromadb.PersistentClient(path=os.path.join(_BASE_DIR, "rag_db"))
        _rag_collection = client.get_or_create_collection("field_marshal_docs")
    except Exception:
        _rag_collection = None


def _rag_query(text: str, n_results: int = 3) -> str:
    if _rag_collection is None:
        return ""
    try:
        results = _rag_collection.query(query_texts=[text], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Bondsman conversation history (module-level, shared with router via getter)
# ---------------------------------------------------------------------------

_bondsman_history: list[dict] = []
_history_lock = threading.Lock()
_MAX_HISTORY = 40


def get_bondsman_history() -> list[dict]:
    with _history_lock:
        return list(_bondsman_history)


def _append_history(role: str, content: str):
    with _history_lock:
        _bondsman_history.append({"role": role, "content": content})
        # Cap history — keep the most recent messages
        if len(_bondsman_history) > _MAX_HISTORY:
            del _bondsman_history[: len(_bondsman_history) - _MAX_HISTORY]


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _llm(
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    timeout: int = 60,
) -> str:
    url = f"{_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    # Qwen3 thinking model returns reasoning_content, not content
    return msg.get("content") or msg.get("reasoning_content", "")


def bondsman_chat(messages: list[dict]) -> str:
    return _llm(_BONDSMAN_MODEL, messages, temperature=0.7, timeout=90)


# ---------------------------------------------------------------------------
# Lord dialectic
# ---------------------------------------------------------------------------

def _lord_opening_challenge(
    caption: str,
    screenshot_b64: Optional[str],
    severity: str,
) -> str:
    """Lord's first challenge against a piece of evidence."""
    content: list = []
    prompt = (
        f"Evidence packet received.\n"
        f"Severity: {severity}\n"
        f"Caption: {caption}\n\n"
        "Examine the evidence. If a screenshot is present, describe exactly what you see. "
        "Issue ONE sharp challenge against the Bondsman's interpretation."
    )
    content.append({"type": "text", "text": prompt})

    if screenshot_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            }
        )

    messages = [
        {"role": "system", "content": _LORD_SYSTEM},
        {"role": "user", "content": content},
    ]
    return _llm(_LORD_MODEL, messages, temperature=0.4, timeout=60)


def _lord_evaluate(challenge: str, bondsman_defense: str) -> str:
    """Lord evaluates Bondsman's defense. Returns [RESOLVED] or a new challenge."""
    messages = [
        {"role": "system", "content": _LORD_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Your challenge was: {challenge}\n\n"
                f"The Bondsman responded: {bondsman_defense}\n\n"
                "Is the challenge resolved? If yes, say [RESOLVED]. "
                "If not, issue a sharper follow-up challenge. One sentence."
            ),
        },
    ]
    return _llm(_LORD_MODEL, messages, temperature=0.3, timeout=60)


def lord_bondsman_dialogue(
    caption: str,
    screenshot_b64: Optional[str],
    severity: str,
    bondsman_history: list[dict],
    max_rounds: int = 3,
) -> list[dict]:
    """
    Run the full Lord/Bondsman dialectic.
    Returns list of exchange dicts to inject into bondsman_history.
    """

    exchanges = []

    # Lord opens
    challenge = _lord_opening_challenge(caption, screenshot_b64, severity)
    exchanges.append({"role": "lord_challenge", "text": challenge})
    _push_event("dialectic", {"speaker": "lord", "text": challenge, "round": 1})

    for round_num in range(1, max_rounds + 1):
        # Build Bondsman's response messages
        msgs = [{"role": "system", "content": _BONDSMAN_SYSTEM}]
        # Include recent bondsman history
        for h in bondsman_history[-10:]:
            if h["role"] in ("user", "assistant"):
                msgs.append(h)
        # Inject the Lord's challenge
        msgs.append(
            {
                "role": "user",
                "content": (
                    f"[LORD CHALLENGE round {round_num}]: {challenge}\n\n"
                    f"Evidence — severity: {severity}, caption: {caption}\n"
                    "Defend with specific facts from the evidence."
                ),
            }
        )

        try:
            defense = bondsman_chat(msgs)
        except Exception as exc:
            defense = f"[Bondsman unavailable: {exc}]"

        exchanges.append({"role": "bondsman_defense", "text": defense, "round": round_num})
        _push_event("dialectic", {"speaker": "bondsman", "text": defense, "round": round_num})

        # Lord evaluates
        try:
            evaluation = _lord_evaluate(challenge, defense)
        except Exception as exc:
            evaluation = f"[Lord unavailable: {exc}]"

        exchanges.append({"role": "lord_evaluation", "text": evaluation, "round": round_num})
        _push_event("dialectic", {"speaker": "lord", "text": evaluation, "round": round_num})

        if "[RESOLVED]" in evaluation:
            break

        if round_num < max_rounds:
            challenge = evaluation  # Sharper challenge becomes next round's challenge
        else:
            # Unresolved after max rounds — flag it
            flag_msg = (
                "Unresolved dialectic. Bondsman's interpretation is flagged. "
                "Address before next dispatch."
            )
            exchanges.append({"role": "flag", "text": flag_msg})
            _push_event("dialectic", {"speaker": "system", "text": flag_msg, "round": round_num})
            _append_history("user", f"[LORD FLAG]: {flag_msg}")

    # Inject exchanges into bondsman history
    for ex in exchanges:
        if ex["role"] == "lord_challenge":
            _append_history("user", f"[LORD]: {ex['text']}")
        elif ex["role"] == "bondsman_defense":
            _append_history("assistant", f"[BONDSMAN DEFENSE]: {ex['text']}")

    return exchanges


# ---------------------------------------------------------------------------
# SSE event push helper
# ---------------------------------------------------------------------------


def _push_event(event_type: str, data: dict):
    """
    Push an SSE-style event to the router process.

    This uses HTTP so it works even when field_marshal.py and router.py run
    as separate OS processes.
    """
    try:
        # POST to the router's event endpoint; router is responsible for
        # broadcasting this to connected SSE clients.
        requests.post(
            f"{_ROUTER_URL}/events",
            json={"type": event_type, "data": data},
            timeout=5,
        )
    except Exception:
        # Best-effort: failure to push an event should not break core logic.
        pass


# ---------------------------------------------------------------------------
# Task dispatch
# ---------------------------------------------------------------------------

def dispatch(target: str, payload) -> dict:
    """Submit a task to the router and poll for completion."""
    try:
        r = requests.post(
            f"{_ROUTER_URL}/task/submit",
            json={"target": target, "payload": payload},
            timeout=10,
        )
        r.raise_for_status()
        task_id = r.json()["task_id"]
    except Exception as exc:
        return {"error": f"dispatch failed: {exc}", "result": None}

    # Poll for completion
    deadline = time.time() + _TASK_MAX
    while time.time() < deadline:
        try:
            r = requests.get(f"{_ROUTER_URL}/task/{task_id}/result", timeout=10)
            r.raise_for_status()
            task = r.json()
            if task["status"] == "completed":
                return task
        except Exception:
            pass
        time.sleep(2)

    return {"error": "task timed out", "task_id": task_id, "result": None}


# ---------------------------------------------------------------------------
# DISPATCH parsing
# ---------------------------------------------------------------------------

_DISPATCH_RE = re.compile(
    r"\[DISPATCH:(\w+)\]\s*(.+?)(?=\n\[DISPATCH:|$)",
    re.DOTALL,
)


def _parse_dispatches(text: str) -> list[tuple[str, Any]]:
    """Extract (target, payload) pairs from Bondsman response text."""
    matches = _DISPATCH_RE.findall(text)
    result = []
    for target, payload_raw in matches:
        payload_raw = payload_raw.strip()
        # For cline/copilot, payload is JSON
        if target in ("cline", "copilot"):
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = payload_raw
        else:
            payload = payload_raw
        result.append((target, payload))
    return result


# ---------------------------------------------------------------------------
# Supervision watcher (background thread)
# ---------------------------------------------------------------------------

def _supervision_watcher():
    """
    Background thread:
    1. Poll agent mid-task messages and have Bondsman reply
    2. Drain evidence queue and run Lord/Bondsman dialectic
    """
    while True:
        time.sleep(3)
        _drain_task_messages()
        _drain_evidence()


def _drain_task_messages():
    """Poll all active tasks for agent messages and have Bondsman respond."""
    try:
        r = requests.get(f"{_ROUTER_URL}/tasks", timeout=5)
        r.raise_for_status()
        tasks = r.json()
    except Exception:
        return

    for task in tasks:
        if task["status"] not in ("claimed",):
            continue
        task_id = task["task_id"]
        try:
            r = requests.get(f"{_ROUTER_URL}/task/{task_id}/messages", timeout=5)
            msgs = r.json() if r.ok else []
        except Exception:
            msgs = []

        for msg in msgs:
            text = msg.get("text", "")
            if not text:
                continue
            # Bondsman replies to agent message
            history = get_bondsman_history()
            msgs_for_llm = [{"role": "system", "content": _BONDSMAN_SYSTEM}]
            for h in history[-8:]:
                if h["role"] in ("user", "assistant"):
                    msgs_for_llm.append(h)
            msgs_for_llm.append(
                {
                    "role": "user",
                    "content": f"[AGENT MESSAGE for task {task_id}]: {text}\nRespond concisely.",
                }
            )
            try:
                reply = bondsman_chat(msgs_for_llm)
                _append_history("user", f"[AGENT:{task['target']}]: {text}")
                _append_history("assistant", reply)
                requests.post(
                    f"{_ROUTER_URL}/task/{task_id}/reply",
                    json={"text": reply},
                    timeout=5,
                )
                _push_event("status", {"event": "agent_reply", "task_id": task_id})
            except Exception:
                pass


def _drain_evidence():
    """Pull pending evidence packets and run Lord/Bondsman dialectic on each."""
    try:
        r = requests.get(f"{_ROUTER_URL}/evidence/pending", timeout=5)
        packets = r.json() if r.ok else []
    except Exception:
        return

    for packet in packets:
        caption = packet.get("caption", "")
        screenshot_b64 = packet.get("screenshot_b64")
        severity = packet.get("severity", "info")
        history = get_bondsman_history()
        try:
            lord_bondsman_dialogue(caption, screenshot_b64, severity, history)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Startup self-test
# ---------------------------------------------------------------------------

def startup_self_test(history: list[dict]):
    """
    Automated startup verification:
    1. Bondsman dispatches a terminal task
    2. Gets result
    3. Lord/Bondsman dialectic fires
    """
    _push_event("status", {"event": "startup_self_test", "phase": "begin"})

    # Bondsman composes the self-test dispatch
    msgs = [
        {"role": "system", "content": _BONDSMAN_SYSTEM},
        {
            "role": "user",
            "content": (
                "Run a startup self-test. Dispatch a simple terminal command to verify "
                "the system is operational. Use [DISPATCH:terminal] syntax."
            ),
        },
    ]

    try:
        response = bondsman_chat(msgs)
    except Exception as exc:
        _push_event("status", {"event": "startup_self_test", "phase": "bondsman_failed", "error": str(exc)})
        return

    _append_history("assistant", response)
    _push_event("status", {"event": "startup_self_test", "phase": "bondsman_responded"})

    dispatches = _parse_dispatches(response)
    if not dispatches:
        # Fallback: dispatch a known-safe command
        dispatches = [("terminal", "echo Field Marshal startup self-test OK")]

    target, payload = dispatches[0]
    task = dispatch(target, payload)

    result_text = str(task.get("result", ""))[:500]
    severity = "error" if task.get("error") else "info"
    caption = f"Startup self-test: {target} agent. Result preview: {result_text[:120]}"

    try:
        lord_bondsman_dialogue(
            caption=caption,
            screenshot_b64=None,
            severity=severity,
            bondsman_history=get_bondsman_history(),
        )
    except Exception:
        pass

    _push_event("status", {"event": "startup_self_test", "phase": "complete"})


# ---------------------------------------------------------------------------
# handle_chat — called by router.py /chat endpoint
# ---------------------------------------------------------------------------

def handle_chat(user_input: str, history: list[dict]) -> str:
    """
    Process human input via the GUI.
    Returns Bondsman's response text. Dispatches any tasks found in the response.
    """
    # RAG retrieval
    rag_context = _rag_query(user_input)

    # Build system prompt (merge RAG context in — LM Studio needs single system msg)
    system_content = _BONDSMAN_SYSTEM
    if rag_context:
        system_content += f"\n\n## Relevant context from knowledge base:\n{rag_context}"

    msgs: list[dict] = [{"role": "system", "content": system_content}]
    # Add recent history
    for h in history[-_MAX_HISTORY:]:
        if h["role"] in ("user", "assistant"):
            msgs.append(h)
    msgs.append({"role": "user", "content": user_input})

    try:
        response = bondsman_chat(msgs)
    except Exception as exc:
        response = f"[Bondsman error: {exc}]"

    # Persist to history
    _append_history("user", user_input)
    _append_history("assistant", response)

    # Parse and execute dispatches (one at a time as per rules)
    dispatches = _parse_dispatches(response)
    if dispatches:
        target, payload = dispatches[0]
        # Run dispatch in background so chat response returns immediately
        threading.Thread(
            target=_execute_dispatch_with_dialectic,
            args=(target, payload),
            daemon=True,
        ).start()

    return response


def _execute_dispatch_with_dialectic(target: str, payload):
    """Background: dispatch task, collect evidence, run dialectic."""
    task = dispatch(target, payload)
    result_text = str(task.get("result", ""))[:500]
    severity = "error" if task.get("error") else "info"
    caption = (
        f"Agent {target} completed task. "
        f"Result: {result_text[:120]}"
    )
    try:
        lord_bondsman_dialogue(
            caption=caption,
            screenshot_b64=None,
            severity=severity,
            bondsman_history=get_bondsman_history(),
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Module initialization
# ---------------------------------------------------------------------------

_init_rag()

# ---------------------------------------------------------------------------
# Entry point (terminal mode — runs startup self-test then loops)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Field Marshal starting up...")
    print(f"Bondsman model: {_BONDSMAN_MODEL}")
    print(f"Lord model: {_LORD_MODEL}")
    print(f"Router: {_ROUTER_URL}")

    # Start supervision watcher thread only when running as a standalone process
    _watcher_thread = threading.Thread(target=_supervision_watcher, daemon=True)
    _watcher_thread.start()

    startup_self_test(get_bondsman_history())
    print("Self-test complete. Field Marshal is operational.")
    print("Running in terminal mode. Ctrl-C to exit.")

    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue
            response = handle_chat(user_input, get_bondsman_history())
            print(f"\nBondsman > {response}")
        except (KeyboardInterrupt, EOFError):
            print("\nField Marshal shutting down.")
            break
