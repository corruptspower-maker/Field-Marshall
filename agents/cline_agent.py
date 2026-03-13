"""
agents/cline_agent.py — Autonomous multi-turn coding agent.

Polls the router for 'cline' tasks, uses LLM to generate code/file changes,
applies them, and reports results. Supports multi-turn conversation with
Field Marshal via the router messaging API.

Protocol tokens:
  <<<FILE: path>>>...<<<END>>>      Write complete file
  <<<PATCH: path>>><<<FIND>>>...<<<REPLACE>>>...<<<END>>>  Patch existing file
  <<<ASK>>>...<<<END>>>             Ask Field Marshal a question
  <<<DONE>>>...<<<END>>>            Signal completion
"""

import json
import os
import re
import subprocess
import time
import uuid
from typing import Optional

import requests

from agents.evidence import capture_screenshot, submit_evidence

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_BASE_DIR, "config.json")) as _f:
    _CFG = json.load(_f)

_ROUTER_URL = f"http://{_CFG['router']['host']}:{_CFG['router']['port']}"
_LMS = _CFG["lmstudio"]
_BASE_LMS_URL = _LMS["base_url"]
_API_TOKEN = _LMS["api_token"]
_BONDSMAN_MODEL = _LMS["llm_model"]
_MAX_OUTPUT = _CFG["limits"]["max_output_bytes"]
_AGENT_ID = f"cline-{uuid.uuid4().hex[:8]}"
_MAX_TURNS = 6


def _lmstudio_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = str(
        os.environ.get("LM_STUDIO_API_TOKEN")
        or os.environ.get("FIELD_MARSHAL_LMSTUDIO_API_TOKEN")
        or _API_TOKEN
        or ""
    ).strip()
    if token and "YOUR_LM_STUDIO" not in token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def _llm(messages: list[dict], temperature: float = 0.3) -> str:
    url = f"{_BASE_LMS_URL}/v1/chat/completions"
    headers = _lmstudio_headers()
    payload = {
        "model": _BONDSMAN_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content", "")


# ---------------------------------------------------------------------------
# Protocol parsing
# ---------------------------------------------------------------------------

_FILE_RE = re.compile(r"<<<FILE:\s*(.+?)>>>(.*?)<<<END>>>", re.DOTALL)
_PATCH_RE = re.compile(
    r"<<<PATCH:\s*(.+?)>>><<<FIND>>>(.*?)<<<REPLACE>>>(.*?)<<<END>>>",
    re.DOTALL,
)
_ASK_RE = re.compile(r"<<<ASK>>>(.*?)<<<END>>>", re.DOTALL)
_DONE_RE = re.compile(r"<<<DONE>>>(.*?)<<<END>>>", re.DOTALL)


def _apply_file(path: str, content: str, working_dir: str) -> str:
    """Write complete file. Returns status message."""
    if not os.path.isabs(path):
        path = os.path.join(working_dir, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    # Open in VS Code
    try:
        subprocess.Popen(
            ["code", "--reuse-window", path],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception:
        pass
    return f"Written: {path}"


def _apply_patch(path: str, find: str, replace: str, working_dir: str) -> str:
    """Patch existing file. Returns status message."""
    if not os.path.isabs(path):
        path = os.path.join(working_dir, path)
    if not os.path.exists(path):
        return f"ERROR: File not found: {path}"
    with open(path, encoding="utf-8") as f:
        original = f.read()
    if find not in original:
        return f"ERROR: FIND text not found in {path}"
    patched = original.replace(find, replace, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    return f"Patched: {path}"


def _ask_fm(task_id: str, question: str) -> str:
    """Send ASK message to Field Marshal and wait for reply."""
    try:
        requests.post(
            f"{_ROUTER_URL}/task/{task_id}/message",
            json={"source": _AGENT_ID, "text": question},
            timeout=10,
        )
    except Exception:
        return "[Ask failed: could not send message]"

    # Wait for reply (up to 60s)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(f"{_ROUTER_URL}/task/{task_id}/reply", timeout=10)
            data = r.json()
            if data.get("text"):
                return data["text"]
        except Exception:
            pass
        time.sleep(3)
    return "[Ask timed out: no reply from Field Marshal]"


# ---------------------------------------------------------------------------
# Main task execution
# ---------------------------------------------------------------------------

def _execute_task(task: dict) -> dict:
    task_id = task["task_id"]
    payload = task.get("payload", {})

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"instruction": payload, "working_dir": ".", "files": []}

    instruction = payload.get("instruction", "")
    working_dir = payload.get("working_dir", ".")
    files_to_read = payload.get("files", [])

    # Build context from files
    file_context = ""
    for rel_path in files_to_read[:5]:  # Limit files read
        full_path = rel_path if os.path.isabs(rel_path) else os.path.join(working_dir, rel_path)
        try:
            with open(full_path, encoding="utf-8", errors="replace") as f:
                content = f.read()[:5000]
            file_context += f"\n\n--- File: {rel_path} ---\n{content}"
        except Exception:
            file_context += f"\n\n--- File: {rel_path} --- (could not read)"

    system_prompt = (
        "You are Cline, an autonomous coding agent. "
        "You implement code changes by outputting structured protocol tokens:\n"
        "  <<<FILE: path>>>file content<<<END>>>  — write complete file\n"
        "  <<<PATCH: path>>><<<FIND>>>old<<<REPLACE>>>new<<<END>>>  — patch file\n"
        "  <<<ASK>>>question<<<END>>>  — ask Field Marshal a question\n"
        "  <<<DONE>>>summary<<<END>>>  — signal task completion\n\n"
        "Always end with <<<DONE>>>. Be precise. No explanations outside tokens."
    )

    messages = [{"role": "system", "content": system_prompt}]
    initial_user = f"Task: {instruction}"
    if file_context:
        initial_user += f"\n\nContext files:{file_context}"
    messages.append({"role": "user", "content": initial_user})

    changes: list[str] = []
    done_summary = ""

    for turn in range(_MAX_TURNS):
        try:
            response = _llm(messages)
        except Exception as exc:
            return {"error": f"LLM call failed on turn {turn + 1}: {exc}", "changes": changes}

        messages.append({"role": "assistant", "content": response})

        # Process FILE writes
        for path, content in _FILE_RE.findall(response):
            status = _apply_file(path.strip(), content, working_dir)
            changes.append(status)

        # Process PATCH operations
        for path, find, replace in _PATCH_RE.findall(response):
            status = _apply_patch(path.strip(), find, replace, working_dir)
            changes.append(status)

        # Process ASK
        asks = _ASK_RE.findall(response)
        for question in asks:
            answer = _ask_fm(task_id, question.strip())
            messages.append({"role": "user", "content": f"Field Marshal replied: {answer}"})

        # Check DONE
        done_matches = _DONE_RE.findall(response)
        if done_matches:
            done_summary = done_matches[-1].strip()
            break

        # Submit intermediate evidence
        submit_evidence(
            task_id=task_id,
            source_agent=_AGENT_ID,
            caption=f"Cline turn {turn + 1}: {len(changes)} changes so far. {str(changes)[:150]}",
            severity="info",
            context={"turn": turn + 1, "changes": changes},
            router_url=_ROUTER_URL,
        )

    return {
        "result": {
            "changes": changes,
            "summary": done_summary or f"Completed {len(changes)} changes",
        },
        "error": None,
    }


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def run():
    print(f"Cline agent {_AGENT_ID} started. Polling {_ROUTER_URL} ...")

    while True:
        try:
            r = requests.post(
                f"{_ROUTER_URL}/task/claim",
                json={"agent_id": _AGENT_ID, "target": "cline"},
                timeout=10,
            )
            task = r.json() if r.ok else {}
        except Exception:
            time.sleep(5)
            continue

        task_id = task.get("task_id")
        if not task_id:
            time.sleep(2)
            continue

        print(f"[{_AGENT_ID}] Claimed task {task_id}")

        result = _execute_task(task)
        changes = result.get("result", {}).get("changes", []) if result.get("result") else []
        summary = result.get("result", {}).get("summary", "") if result.get("result") else ""
        has_error = bool(result.get("error"))

        screenshot = capture_screenshot() if has_error else None

        submit_evidence(
            task_id=task_id,
            source_agent=_AGENT_ID,
            caption=(
                f"Cline task complete. {len(changes)} file operations. "
                f"Summary: {summary[:200]}"
            ),
            severity="error" if has_error else "info",
            context={"changes": changes, "summary": summary},
            screenshot=screenshot,
            router_url=_ROUTER_URL,
        )

        try:
            requests.post(
                f"{_ROUTER_URL}/task/{task_id}/complete",
                json=result,
                timeout=10,
            )
        except Exception:
            pass

        time.sleep(1)


if __name__ == "__main__":
    run()
