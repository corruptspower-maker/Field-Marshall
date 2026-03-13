"""Configuration loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_app_config(config_path: str | Path) -> tuple[dict[str, Any], Path]:
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    root_dir = path.parent.parent
    return data, root_dir


def require_config(config: dict[str, Any], key_path: str) -> Any:
    current: Any = config
    for part in key_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Missing required config key: {key_path}")
        current = current[part]
    return current
