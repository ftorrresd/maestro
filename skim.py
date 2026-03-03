#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

_SRC_PATH = Path(__file__).resolve().parent / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from maestro.cli import main
from maestro.config import SkimConfig, load_config as _load_config
from maestro.skimmer import run_from_config, skim_file

__all__ = [
    "SkimConfig",
    "_load_config",
    "main",
    "run_from_config",
    "skim_file",
]


if __name__ == "__main__":
    main()
