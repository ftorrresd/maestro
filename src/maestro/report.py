from __future__ import annotations

from typing import Any


def build_report(
    *,
    input_file: str,
    output_file: str,
    tree: str,
    input_config: dict[str, Any],
    sample_metadata: dict[str, Any],
    offset: int,
    n_events: int,
    entry_start: int,
    entry_stop: int,
    n_scanned: int,
    n_selected: int,
    requested_triggers: list[str],
    active_triggers: list[str],
    missing_triggers: list[str],
    object_requirements: dict[str, int],
    missing_object_branches: list[str],
    cutflow_labels: list[str],
    cutflow_counts: list[int],
    kept_branches: list[str],
    corrections: dict[str, Any],
) -> dict[str, Any]:
    return {
        "input_file": input_file,
        "output_file": output_file,
        "tree": tree,
        "input_config": input_config,
        "sample_metadata": sample_metadata,
        "requested_event_range": {
            "offset": offset,
            "n_events": n_events,
        },
        "processed_event_range": {
            "entry_start": entry_start,
            "entry_stop": entry_stop,
            "n_scanned": n_scanned,
            "n_selected": n_selected,
            "selection_efficiency": (float(n_selected) / n_scanned)
            if n_scanned
            else 0.0,
        },
        "selection": {
            "requested_triggers": requested_triggers,
            "active_triggers": active_triggers,
            "missing_triggers": missing_triggers,
            "missing_triggers_default_false": True,
            "object_requirements": object_requirements,
            "missing_object_branches": missing_object_branches,
        },
        "cutflow": {
            "labels": cutflow_labels,
            "counts": cutflow_counts,
        },
        "kept_branches": kept_branches,
        "corrections": corrections,
    }
