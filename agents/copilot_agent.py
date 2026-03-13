"""
agents/copilot_agent.py — Code review agent.

Polls the router for 'copilot' tasks, performs LLM-based code review,
writes COPILOT_RESULT.md beside the reviewed file, and reports results.
"""

import json
import os
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
_AGENT_ID = f"copilot-{uuid.uuid4().hex[:8]}"

# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def _llm(messages: list[dict], temperature: float = 0.3) -> str:
    url = f"{_BASE_LMS_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_API_TOKEN}",
        "Content-Type": "application/json",
    }
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
# Review execution
# ---------------------------------------------------------------------------

def _execute_review(task: dict) -> dict:
    task_id = task["task_id"]
    payload = task.get("payload", {})

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"instruction": payload, "file": "", "working_dir": "."}

    instruction = payload.get("instruction", "Review this code for issues.")
    file_path = payload.get("file", "")
    working_dir = payload.get("working_dir", ".")

    # Resolve file path
    if file_path and not os.path.isabs(file_path):
        file_path = os.path.join(working_dir, file_path)

    # Read file content
    file_content = ""
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                file_content = f.read()[:20000]  # Limit to 20KB
        except Exception as exc:
            return {"error": f"Could not read file: {exc}", "result": None}
    elif file_path:
        return {"error": f"File not found: {file_path}", "result": None}

    system_prompt = (
        "You are Copilot, a code review agent. "
        "Your job is to review code for security vulnerabilities, bugs, "
        "performance issues, and code quality problems. "
        "Be specific. List each issue with:\n"
        "  - Severity: critical/high/medium/low\n"
        "  - Line reference if applicable\n"
        "  - Description of the issue\n"
        "  - Recommended fix\n\n"
        "Format your output as Markdown suitable for a COPILOT_RESULT.md file."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Instruction: {instruction}\n\n"
                f"File: {file_path or '(no file provided)'}\n\n"
                f"```\n{file_content}\n```"
                if file_content
                else f"Instruction: {instruction}\n\nNo file content provided."
            ),
        },
    ]

    try:
        review_text = _llm(messages)
    except Exception as exc:
        return {"error": f"LLM call failed: {exc}", "result": None}

    # Write COPILOT_RESULT.md
    if file_path:
        result_dir = os.path.dirname(file_path)
    else:
        result_dir = working_dir

    result_md_path = os.path.join(result_dir, "COPILOT_RESULT.md")
    header = (
        f"# Copilot Code Review\n\n"
        f"**File:** `{file_path or 'N/A'}`  \n"
        f"**Instruction:** {instruction}  \n"
        f"**Agent:** {_AGENT_ID}  \n\n"
        f"---\n\n"
    )

    try:
        with open(result_md_path, "w", encoding="utf-8") as f:
            f.write(header + review_text)
    except Exception as exc:
        return {"error": f"Could not write COPILOT_RESULT.md: {exc}", "result": None}

    # Open both files in VS Code
    for path_to_open in [file_path, result_md_path]:
        if path_to_open and os.path.exists(path_to_open):
            try:
                subprocess.Popen(
                    ["code", "--reuse-window", path_to_open],
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except Exception:
                pass

    return {
        "result": {
            "review": review_text,
            "result_file": result_md_path,
            "reviewed_file": file_path,
        },
        "error": None,
    }


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def run():
    print(f"Copilot agent {_AGENT_ID} started. Polling {_ROUTER_URL} ...")

    while True:
        try:
            r = requests.post(
                f"{_ROUTER_URL}/task/claim",
                json={"agent_id": _AGENT_ID, "target": "copilot"},
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

        result = _execute_review(task)
        has_error = bool(result.get("error"))

        screenshot = capture_screenshot() if has_error else None

        review_summary = ""
        if result.get("result") and result["result"].get("review"):
            review_summary = result["result"]["review"][:300]

        submit_evidence(
            task_id=task_id,
            source_agent=_AGENT_ID,
            caption=(
                f"Copilot review complete for "
                f"{result.get('result', {}).get('reviewed_file', 'unknown') if result.get('result') else 'unknown'}. "
                f"Preview: {review_summary[:150]}"
            ),
            severity="error" if has_error else "info",
            context={
                "result_file": result.get("result", {}).get("result_file", "") if result.get("result") else "",
                "reviewed_file": result.get("result", {}).get("reviewed_file", "") if result.get("result") else "",
                "error": result.get("error"),
            },
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
