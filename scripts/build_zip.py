"""Build a reproducibility zip bundle for the project."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Field Marshal zip bundle")
    parser.add_argument(
        "--output",
        default=str(ROOT_DIR / "Field-Marshall-bundle"),
        help="Output path without extension",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).resolve()
    archive = shutil.make_archive(str(output), "zip", ROOT_DIR)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
