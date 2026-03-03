from __future__ import annotations

from typing import Any, Mapping

from ..skimmer import run_from_config


def run_configs_locally(configs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [run_from_config(config) for config in configs]
