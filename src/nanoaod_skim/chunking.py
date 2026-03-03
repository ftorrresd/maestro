from __future__ import annotations

from typing import Union

StepSize = Union[str, int]


def normalize_step_size(step_size: StepSize) -> StepSize:
    if isinstance(step_size, int):
        return step_size
    stripped = step_size.strip()
    return int(stripped) if stripped.isdigit() else step_size


def compute_entry_range(
    total_entries: int,
    *,
    offset: int,
    n_events: int,
) -> tuple[int, int]:
    entry_start = min(offset, total_entries)
    entry_stop = (
        total_entries if n_events < 0 else min(total_entries, entry_start + n_events)
    )
    return entry_start, entry_stop
