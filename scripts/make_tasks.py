#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from maestro.runners.gnu_parallel import render_parallel_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate GNU Parallel task list")
    parser.add_argument("--manifest", required=True, help="Input JSON list of configs")
    parser.add_argument("--output", required=True, help="Output tasks file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)

    with manifest_path.open("r", encoding="utf-8") as handle:
        configs = json.load(handle)
    if not isinstance(configs, list):
        raise ValueError("Manifest must be a JSON array of config objects.")

    tasks = render_parallel_tasks(configs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(tasks)


if __name__ == "__main__":
    main()
