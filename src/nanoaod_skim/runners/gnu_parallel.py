from __future__ import annotations

import json
from typing import Any, Mapping


def render_parallel_tasks(configs: list[Mapping[str, Any]]) -> str:
    lines = []
    for config in configs:
        payload = json.dumps(dict(config), separators=(",", ":"))
        lines.append(f"python skim.py '{payload}'")
    return "\n".join(lines)
