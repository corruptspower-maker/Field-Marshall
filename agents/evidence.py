"""
agents/evidence.py — Shared evidence utilities for all agents.

Provides:
- capture_screenshot() -> str | None  (base64 PNG via PowerShell)
- submit_evidence(...)  -> bool        (POST to router /evidence)
"""

import base64
import json
import subprocess
import sys
import time
from typing import Optional

import requests


def capture_screenshot() -> Optional[str]:
    """
    Capture the current screen using PowerShell System.Windows.Forms.
    Returns base64-encoded PNG string, or None if capture fails.
    Only works on Windows.
    """
    if sys.platform != "win32":
        return None

    ps_script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$ms = New-Object System.IO.MemoryStream
$bitmap.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
$bytes = $ms.ToArray()
[Convert]::ToBase64String($bytes)
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Validate it's valid base64
            b64 = result.stdout.strip()
            base64.b64decode(b64)  # will raise if invalid
            return b64
    except Exception:
        pass
    return None


def submit_evidence(
    task_id: str,
    source_agent: str,
    caption: str,
    severity: str = "info",
    context: Optional[dict] = None,
    screenshot: Optional[str] = None,
    router_url: str = "http://127.0.0.1:5000",
) -> bool:
    """
    Submit an evidence packet to the router /evidence endpoint.
    Never raises — returns True on success, False on failure.
    """
    packet = {
        "task_id": task_id,
        "source_agent": source_agent,
        "timestamp": time.time(),
        "severity": severity,
        "caption": caption,
        "screenshot_b64": screenshot,
        "context": context or {},
    }
    try:
        r = requests.post(
            f"{router_url}/evidence",
            json=packet,
            timeout=10,
        )
        return r.ok
    except Exception:
        return False
