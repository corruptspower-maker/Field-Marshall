# Field Marshal — Local AI Orchestration System

> *"Capability ≠ Sovereignty"* — A small model supervises a large one.

A fully autonomous, zero-cloud AI orchestration framework. Runs entirely on Windows using **LM Studio** as a local model server. Two LLMs. Three agents. One law.

---

## Architecture

```
                        ┌─────────────────────────────┐
   Human ──────────────►│         Bondsman            │
   (GUI chat only)      │    (Qwen3.5-9B campaign mind)│
                        │  holds context, commands     │
                        │  agents, defends to Lord     │
                        └──────────┬──────────────────┘
                                   │ challenges/defenses
                        ┌──────────▼──────────────────┐
                        │           Lord              │
                        │ (Granite Vision 3.2 2B)     │
                        │  sees screenshots, issues   │
                        │  adversarial challenges     │
                        │  NEVER commands agents      │
                        └─────────────────────────────┘
                                   │ dispatch
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │   terminal   │    │    cline     │    │   copilot    │
    │  PowerShell  │    │  LLM coder   │    │ code review  │
    │    agent     │    │    agent     │    │    agent     │
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           │                   │                   │
           └───────────────────┴───────────────────┘
                           evidence packets
                    (screenshot + caption + severity)
                               │
                        ┌──────▼──────┐
                        │   Router    │
                        │  Flask API  │
                        │  + GUI :5000│
                        └─────────────┘
```

**The Core Law:** Capability ≠ Sovereignty. The smaller Lord model supervises the larger Bondsman. The Bondsman commands the agents. The Lord challenges the Bondsman's interpretations. The human only talks to the Bondsman.

---

## Communication Rules

| From → To | Allowed |
|-----------|---------|
| Human → Bondsman | ✅ YES (via GUI chat) |
| Bondsman → Agents | ✅ YES (dispatch tasks) |
| Agents → Bondsman | ✅ YES (evidence packets, mid-task messages) |
| Bondsman ↔ Lord | ✅ YES (dialectic challenges and defenses) |
| Lord → Agents | ❌ NO (Law 9 — Lord never commands agents) |
| Human → Lord | ❌ NO (human only talks to Bondsman) |
| Agent ↔ Agent | ❌ NO (agents are independent) |

---

## Project Structure

```
Field-Marshal/
│
├── README.md                     # This file
├── requirements.txt              # Flask, requests, chromadb
├── config.json                   # All settings
├── .gitignore
├── safety_rules.json             # Allow/deny patterns for terminal commands
│
├── INSTALL.bat                   # One-time: pip install + rag index
├── LAUNCH.bat                    # Opens all services in Windows Terminal tabs
├── MAKE_ZIP.bat                  # Package to Desktop zip
│
├── _start_router.cmd             # Per-service launchers
├── _start_agent.cmd
├── _start_cline.cmd
├── _start_copilot.cmd
├── _start_fieldmarshal.cmd
│
├── personas/
│   ├── bondsman.md               # Bondsman character, doctrine, dispatch syntax
│   └── lord.md                   # Lord character, adversarial stance, rules
│
├── router.py                     # Flask app — task queue + evidence queue + GUI
├── field_marshal.py              # Lord + Bondsman brain + supervision loop
├── rag_index.py                  # ChromaDB + nomic-embed indexer
├── smoke_test.py                 # Pre-launch verification
│
├── agents/
│   ├── __init__.py
│   ├── evidence.py               # Screenshot capture + evidence submission
│   ├── terminal_agent.py         # PowerShell execution agent
│   ├── cline_agent.py            # Autonomous coding agent
│   └── copilot_agent.py          # Code review agent
│
├── static/
│   ├── style.css                 # Dashboard dark theme
│   └── app.js                    # Chat + live feed JS (SSE)
│
├── templates/
│   └── dashboard.html            # Main GUI
│
└── ps_screenshot.ps1             # PowerShell screen capture utility
```

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| OS | Windows 10/11 (PowerShell required) |
| Python | 3.10+ with pip |
| LM Studio | Running with API server on port 1234 |
| Bondsman model | `qwen/qwen3.5-9b` (or compatible Qwen3.5 9B) |
| Lord model | `ibm-granite/granite-vision-3.2-2b` (vision-capable) |
| VS Code | Optional — for viewing agent file output |

---

## Setup

### 1. Load Models in LM Studio

Open LM Studio → Models tab → load both:
- `qwen/qwen3.5-9b` (Bondsman)
- `ibm-granite/granite-vision-3.2-2b` (Lord)

Enable the API server: LM Studio → Developer → Start Server (port 1234)

### 2. Install Dependencies

```bat
INSTALL.bat
```

This runs `pip install -r requirements.txt` and optionally indexes your `docs/` folder into ChromaDB for RAG.

### 3. Verify Setup

```bat
python smoke_test.py
```

All 6 tests should pass. Fix any failures before launching.

### 4. Launch

```bat
LAUNCH.bat
```

Opens 5 Windows Terminal tabs (router, terminal agent, cline agent, copilot agent, field marshal brain) and opens `http://localhost:5000` in your browser.

---

## Configuration

Edit `config.json`:

```json
{
  "router": { "host": "127.0.0.1", "port": 5000, "debug": false },
  "lmstudio": {
    "base_url": "http://localhost:1234",
    "api_token": "sk-lm-...",
    "llm_model": "qwen/qwen3.5-9b",
    "lord_model": "ibm-granite/granite-vision-3.2-2b",
    "embed_model": "text-embedding-nomic-embed-text-v1.5-embedding"
  },
  "safety_mode": "safe",
  "timeouts": { "task_default": 30, "task_max": 300, "agent_claim_timeout": 60 },
  "limits": { "max_output_bytes": 104857, "max_log_days": 7 }
}
```

Set `"safety_mode": "unsafe"` to disable command allow/deny filtering (not recommended).

---

## Usage

Once LAUNCH.bat is running:

1. Open `http://localhost:5000` in your browser
2. Type your objective in the chat box (Ctrl+Enter to send)
3. The Bondsman processes your request and may dispatch agents
4. Watch the live feed panel for real-time agent activity and Lord/Bondsman dialectic
5. Agents execute autonomously — you are NOT in the loop during execution

### Example Objectives

```
List the top 10 processes by CPU usage on this machine.
```

```
Review C:\projects\myapp\auth.py for security vulnerabilities.
```

```
Write a Python script that reads all .log files in C:\logs and outputs a summary.
```

---

## Evidence Flow

Every agent action produces an **evidence packet**:

```json
{
  "task_id": "uuid",
  "source_agent": "terminal-abc123",
  "timestamp": 1710000000.0,
  "severity": "info | warn | error",
  "caption": "What happened",
  "screenshot_b64": "base64 PNG or null",
  "context": { "command": "...", "returncode": 0 }
}
```

When evidence arrives:
1. **Lord** opens with a challenge (uses vision on screenshot if present)
2. **Bondsman** defends with specific facts from the evidence
3. **Lord** evaluates: replies `[RESOLVED]` if satisfied, or sharpens the challenge
4. Repeat up to 3 rounds
5. Unresolved after 3 rounds: Bondsman's history is flagged

---

## RAG Knowledge Base

Place `.md` or `.txt` files in a `docs/` directory, then run:

```bat
python rag_index.py --docs docs --reset
```

The Bondsman will retrieve relevant context from this knowledge base for each chat message.

---

## Roadmap

- [ ] Persistent campaign logging (SQLite)
- [ ] Multi-agent parallel dispatch
- [ ] Web-based evidence viewer with screenshot gallery
- [ ] Campaign state save/restore
- [ ] Linux/macOS port (replace PowerShell with bash agents)
- [ ] Voice interface for hands-free operation

---

## Author's Assessment

Field Marshal is an experiment in **adversarial AI supervision**. The core thesis is that you don't need a large model to supervise a large model — you need an adversarial one. The Lord (2B parameters) cannot outthink the Bondsman (9B parameters) on any given task. But it doesn't need to. It only needs to challenge specific claims about specific evidence. That's a much narrower problem.

The architecture is deliberately asymmetric: the Bondsman has breadth (campaign context, multi-step reasoning, dispatch authority), while the Lord has focus (single-point challenges, evidence verification, resolution authority). Neither can do the other's job well. That's the point.

What makes this architecture interesting: it's not a safety layer. It's a dialectic. The Lord doesn't prevent the Bondsman from acting — it demands that the Bondsman justify its interpretations of evidence. The human benefits not by approving actions, but by reading the dialectic transcript and understanding *why* the system did what it did.

This is early-stage infrastructure. The interesting problems (campaign persistence, evidence archaeology, multi-step planning failure modes) are unsolved. But the bones are right.
