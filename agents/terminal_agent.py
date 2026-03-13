"""
agents/terminal_agent.py — PowerShell execution agent.

Polls the router for 'terminal' tasks, executes them via PowerShell,
and reports results back.
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid

import requests

from agents.evidence import capture_screenshot, submit_evidence

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_BASE_DIR, "config.json")) as _f:
    _CFG = json.load(_f)

_ROUTER_URL = f"http://{_CFG['router']['host']}:{_CFG['router']['port']}"
_MAX_OUTPUT = _CFG["limits"]["max_output_bytes"]
_SAFETY_MODE = _CFG.get("safety_mode", "safe")

with open(os.path.join(_BASE_DIR, "safety_rules.json")) as _f:
    _SAFETY_RULES = json.load(_f)

_AGENT_ID = f"terminal-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Safety check
# ---------------------------------------------------------------------------

def _is_safe(command: str) -> bool:
    rules = _SAFETY_RULES.get(_SAFETY_MODE, {})
    deny_patterns = rules.get("deny_patterns", [])
    for pattern in deny_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return False
    allow_patterns = rules.get("allow_patterns", [])
    if not allow_patterns:
        return True  # No allow list means everything not denied is allowed
    for pattern in allow_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    # If allow_patterns defined and none matched, deny
    return False


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------

def _run_command(command: str) -> tuple[int, str, str]:
    """Execute command via PowerShell. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=_CFG["timeouts"]["task_max"],
        )
        stdout = result.stdout[:_MAX_OUTPUT]
        stderr = result.stderr[:_MAX_OUTPUT]
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        # PowerShell not available (non-Windows) — simulate for testing
        return -1, "", "powershell not found (non-Windows environment)"
    except Exception as exc:
        return -1, "", str(exc)


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def run():
    print(f"Terminal agent {_AGENT_ID} started. Polling {_ROUTER_URL} ...")

    while True:
        # Claim a task
        try:
            r = requests.post(
                f"{_ROUTER_URL}/task/claim",
                json={"agent_id": _AGENT_ID, "target": "terminal"},
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

        command = task.get("payload", "")
        print(f"[{_AGENT_ID}] Claimed task {task_id}: {str(command)[:80]}")

        # Safety check
        if not _is_safe(str(command)):
            error_msg = f"Command blocked by safety rules: {str(command)[:100]}"
            print(f"[{_AGENT_ID}] BLOCKED: {error_msg}")
            screenshot = capture_screenshot()
            submit_evidence(
                task_id=task_id,
                source_agent=_AGENT_ID,
                caption=error_msg,
                severity="error",
                context={"command": str(command)[:500], "blocked": True},
                screenshot=screenshot,
                router_url=_ROUTER_URL,
            )
            try:
                requests.post(
                    f"{_ROUTER_URL}/task/{task_id}/complete",
                    json={"result": None, "error": error_msg},
                    timeout=10,
                )
            except Exception:
                pass
            continue

        # Execute
        returncode, stdout, stderr = _run_command(str(command))
        success = returncode == 0
        severity = "info" if success else "error"
        output_text = stdout or stderr or "(no output)"

        print(f"[{_AGENT_ID}] Task {task_id} exit code: {returncode}")

        # Screenshot on failure (mandatory), optional on success
        screenshot = None
        if not success:
            screenshot = capture_screenshot()
        # On success we skip screenshot to keep evidence lightweight

        caption = (
            f"Terminal agent executed: {str(command)[:80]}. "
            f"Exit code: {returncode}. Output: {output_text[:200]}"
        )

        submit_evidence(
            task_id=task_id,
            source_agent=_AGENT_ID,
            caption=caption,
            severity=severity,
            context={
                "command": str(command)[:500],
                "returncode": returncode,
                "stdout": stdout[:1000],
                "stderr": stderr[:500],
            },
            screenshot=screenshot,
            router_url=_ROUTER_URL,
        )

        # Report result
        result_payload = {
            "result": {
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "output": output_text,
            },
            "error": stderr if not success else None,
        }
        try:
            requests.post(
                f"{_ROUTER_URL}/task/{task_id}/complete",
                json=result_payload,
                timeout=10,
            )
        except Exception:
            pass

        # Brief pause before next poll
        time.sleep(1)


if __name__ == "__main__":
    run()
