"""Canonical deterministic bootstrap for Field Marshal Factory."""

from __future__ import annotations

import argparse
import shlex
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from field_marshal.api.app import create_app  # noqa: E402
from field_marshal.utils.config import load_app_config, require_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Field Marshal Factory bootstrap")
    parser.add_argument(
        "--config",
        default="config/app.yaml",
        help="Path to app config YAML",
    )
    parser.add_argument(
        "--services-config",
        default="config/services.yaml",
        help="Path to services config YAML",
    )
    parser.add_argument(
        "--open-ui",
        action="store_true",
        help="Open browser UI after startup",
    )
    return parser.parse_args()


def load_services_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def verify_port_available(host: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError(f"Port {host}:{port} is already in use")
    finally:
        sock.close()


def start_workers(services_config: dict) -> list[subprocess.Popen]:
    workers = services_config.get("workers", {})
    processes: list[subprocess.Popen] = []
    for name, cfg in workers.items():
        if not isinstance(cfg, dict) or not cfg.get("enabled"):
            continue
        command = str(cfg.get("command", "")).strip()
        if not command:
            continue
        proc = subprocess.Popen(  # noqa: S603
            shlex.split(command),
            cwd=ROOT_DIR,
        )
        processes.append(proc)
        print(f"[bootstrap] started worker '{name}' pid={proc.pid}")
    return processes


def run_health_check(app) -> None:
    with app.test_client() as client:
        response = client.get("/health")
        if response.status_code != 200:
            raise RuntimeError(
                f"Health check failed with status {response.status_code}: {response.get_data(as_text=True)}"
            )


def maybe_open_ui(host: str, port: int) -> None:
    url = f"http://{host}:{port}"
    # Allow Flask time to bind before opening.
    time.sleep(0.2)
    webbrowser.open(url)


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (ROOT_DIR / config_path).resolve()

    services_path = Path(args.services_config)
    if not services_path.is_absolute():
        services_path = (ROOT_DIR / services_path).resolve()

    config, _ = load_app_config(config_path)
    host = str(require_config(config, "api.host"))
    port = int(require_config(config, "api.port"))
    debug = bool(config["api"].get("debug", False))
    open_ui = bool(args.open_ui or config.get("bootstrap", {}).get("open_ui", False))
    run_check = bool(config.get("bootstrap", {}).get("run_health_check", True))

    verify_port_available(host, port)
    app = create_app(config_path)
    if run_check:
        run_health_check(app)

    services_config = load_services_config(services_path)
    workers = start_workers(services_config)

    print("[bootstrap] config validated")
    print(f"[bootstrap] db initialized at {app.extensions['db'].db_path}")
    print(f"[bootstrap] api starting on http://{host}:{port}")
    print(f"[bootstrap] workers started: {len(workers)}")

    if open_ui:
        maybe_open_ui(host, port)

    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        for proc in workers:
            proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
