"""Development launcher for the new spine."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "bootstrap.py"),
        "--config",
        str(ROOT_DIR / "config" / "app.yaml"),
    ]
    return subprocess.call(command)  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
