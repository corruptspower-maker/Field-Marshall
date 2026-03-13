"""
smoke_test.py — Pre-launch verification for Field Marshal.

Tests:
  1. LM Studio reachable, list loaded models
  2. Bondsman (Qwen) responds to text
  3. Lord (Granite) responds to text
  4. Lord responds to a screenshot (vision test)
  5. Router is reachable
  6. Full mini Lord/Bondsman dialectic

Run: python smoke_test.py
"""

import base64
import json
import os
import sys
import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_BASE_DIR, "config.json")) as f:
    CFG = json.load(f)

LMS = CFG["lmstudio"]
BASE_URL = LMS["base_url"]
API_TOKEN = LMS["api_token"]
BONDSMAN_MODEL = LMS["llm_model"]
LORD_MODEL = LMS["lord_model"]
ROUTER_URL = f"http://{CFG['router']['host']}:{CFG['router']['port']}"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "", fix: str = ""):
    status = PASS if ok else FAIL
    print(f"  {status} {name}")
    if detail:
        print(f"        {detail}")
    if not ok and fix:
        print(f"        \033[93mFIX:\033[0m {fix}")
    _results.append((name, ok, detail))
    return ok


def llm_call(model: str, messages: list[dict], screenshot_b64: Optional[str] = None) -> str:
    content = messages[-1]["content"]

    if screenshot_b64:
        # Vision call: content becomes an array
        messages[-1]["content"] = [
            {"type": "text", "text": content if isinstance(content, str) else str(content)},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            },
        ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "stream": False,
    }
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content", "")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_lmstudio_reachable():
    print("\n1. LM Studio connectivity")
    try:
        r = requests.get(f"{BASE_URL}/v1/models", headers=HEADERS, timeout=10)
        r.raise_for_status()
        models = r.json().get("data", [])
        model_ids = [m["id"] for m in models]
        print(f"   {INFO} Loaded models: {', '.join(model_ids) or '(none)'}")
        check(
            "LM Studio reachable",
            True,
            f"{len(models)} model(s) loaded",
        )
        bondsman_ok = any(BONDSMAN_MODEL.lower() in mid.lower() for mid in model_ids)
        check(
            f"Bondsman model loaded ({BONDSMAN_MODEL})",
            bondsman_ok,
            fix=f"Load {BONDSMAN_MODEL} in LM Studio before launching.",
        )
        lord_ok = any(LORD_MODEL.lower() in mid.lower() for mid in model_ids)
        check(
            f"Lord model loaded ({LORD_MODEL})",
            lord_ok,
            fix=f"Load {LORD_MODEL} in LM Studio before launching.",
        )
    except Exception as exc:
        check(
            "LM Studio reachable",
            False,
            str(exc),
            fix="Ensure LM Studio is running on port 1234 with API server enabled.",
        )


def test_bondsman_text():
    print("\n2. Bondsman text response")
    try:
        response = llm_call(
            BONDSMAN_MODEL,
            [
                {"role": "system", "content": "You are the Bondsman. Reply in one sentence."},
                {"role": "user", "content": "Confirm you are operational."},
            ],
        )
        ok = bool(response and len(response) > 5)
        check("Bondsman responds to text", ok, response[:120] if ok else "Empty response")
    except Exception as exc:
        check(
            "Bondsman responds to text",
            False,
            str(exc),
            fix=f"Ensure {BONDSMAN_MODEL} is loaded and responding.",
        )


def test_lord_text():
    print("\n3. Lord text response")
    try:
        response = llm_call(
            LORD_MODEL,
            [
                {"role": "system", "content": "You are the Lord. Reply in one sentence."},
                {"role": "user", "content": "Confirm you are operational."},
            ],
        )
        ok = bool(response and len(response) > 5)
        check("Lord responds to text", ok, response[:120] if ok else "Empty response")
    except Exception as exc:
        check(
            "Lord responds to text",
            False,
            str(exc),
            fix=f"Ensure {LORD_MODEL} is loaded and responding.",
        )


def test_lord_vision():
    print("\n4. Lord vision test")
    # Create a minimal 1x1 PNG as test image
    # PNG header + IHDR + IDAT + IEND for a 1x1 white pixel
    minimal_png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    try:
        response = llm_call(
            LORD_MODEL,
            [
                {
                    "role": "system",
                    "content": "You are the Lord. Describe what you see in the image briefly.",
                },
                {"role": "user", "content": "What is in this image?"},
            ],
            screenshot_b64=minimal_png_b64,
        )
        ok = bool(response and len(response) > 5)
        check(
            "Lord responds to screenshot (vision)",
            ok,
            response[:120] if ok else "Empty response",
            fix=f"Ensure {LORD_MODEL} supports vision (image_url content type).",
        )
    except Exception as exc:
        check(
            "Lord responds to screenshot (vision)",
            False,
            str(exc),
            fix=f"Ensure {LORD_MODEL} supports vision and is properly loaded.",
        )


def test_router():
    print("\n5. Router health check")
    try:
        r = requests.get(f"{ROUTER_URL}/health", timeout=5)
        r.raise_for_status()
        data = r.json()
        check(
            "Router /health reachable",
            data.get("status") == "ok",
            f"tasks_active={data.get('tasks_active')}, evidence_pending={data.get('evidence_pending')}",
            fix="Run: python router.py (or LAUNCH.bat) before smoke_test.py",
        )
    except Exception as exc:
        check(
            "Router /health reachable",
            False,
            str(exc),
            fix=f"Start router.py on {ROUTER_URL} before running smoke_test.py",
        )


def test_mini_dialectic():
    print("\n6. Mini Lord/Bondsman dialectic")
    try:
        # Bondsman makes a claim
        claim = llm_call(
            BONDSMAN_MODEL,
            [
                {"role": "system", "content": "You are the Bondsman. Be concise."},
                {
                    "role": "user",
                    "content": "Describe the result of running 'echo hello' as if it just succeeded.",
                },
            ],
        )
        check("Bondsman produced a claim", bool(claim and len(claim) > 5), claim[:100])

        # Lord challenges it
        challenge = llm_call(
            LORD_MODEL,
            [
                {
                    "role": "system",
                    "content": "You are the Lord. Issue ONE sharp challenge. Be terse.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Evidence caption: {claim[:200]}\n"
                        "Severity: info\n"
                        "Issue ONE sharp challenge."
                    ),
                },
            ],
        )
        check("Lord issued a challenge", bool(challenge and len(challenge) > 5), challenge[:100])

        # Bondsman defends
        defense = llm_call(
            BONDSMAN_MODEL,
            [
                {"role": "system", "content": "You are the Bondsman. Defend with facts."},
                {
                    "role": "user",
                    "content": f"[LORD CHALLENGE]: {challenge}\n\nDefend your claim.",
                },
            ],
        )
        check("Bondsman defended", bool(defense and len(defense) > 5), defense[:100])

        # Lord resolves or escalates
        resolution = llm_call(
            LORD_MODEL,
            [
                {
                    "role": "system",
                    "content": "You are the Lord. Say [RESOLVED] if satisfied, or a sharper challenge.",
                },
                {
                    "role": "user",
                    "content": f"Challenge: {challenge}\nDefense: {defense}\nResolve or escalate.",
                },
            ],
        )
        resolved = "[RESOLVED]" in resolution
        check(
            "Lord evaluated (resolved or escalated)",
            bool(resolution and len(resolution) > 5),
            f"{'[RESOLVED]' if resolved else '[CHALLENGED]'}: {resolution[:100]}",
        )

    except Exception as exc:
        check("Mini dialectic", False, str(exc))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary():
    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    for name, ok, _ in _results:
        status = PASS if ok else FAIL
        print(f"  {status} {name}")
    print(f"\n{passed}/{total} checks passed.")
    if passed == total:
        print("\n\033[92mAll checks passed. Ready to LAUNCH.bat\033[0m")
    else:
        print(f"\n\033[91m{total - passed} check(s) failed. Fix issues above before launching.\033[0m")
    return passed == total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Field Marshal — Smoke Test")
    print("=" * 60)

    test_lmstudio_reachable()
    test_bondsman_text()
    test_lord_text()
    test_lord_vision()
    test_router()
    test_mini_dialectic()

    ok = print_summary()
    sys.exit(0 if ok else 1)
