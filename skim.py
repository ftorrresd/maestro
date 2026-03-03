#!/usr/bin/env python3
"""CMS NanoAOD skimmer using uproot + awkward.

Strategy
--------
1) Read the `Events` tree in chunks (`tree.iterate`) to keep memory bounded.
2) Build a cumulative event mask from trigger OR + object-count requirements.
3) Keep only selected events and concatenate chunk outputs.
4) Write skimmed events, cutflow histogram, and JSON report.

Inputs
------
- Input ROOT file with a NanoAOD-like `Events` tree.
- JSON config validated by `SkimConfig`.
- Optional CLI knobs: tree name and iteration step size.

Outputs
-------
- Output ROOT file containing skimmed `Events` and `cutflow` histogram.
- Output report JSON (`<output>.report.json`) with selection metadata and counts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union, cast

import awkward as ak
import numpy as np
import uproot
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

StepSize = Union[str, int]


class SkimConfig(BaseModel):
    """Validated skimming configuration."""

    model_config = ConfigDict(extra="forbid")

    input: str
    output: str
    tree: str = "Events"
    step_size: StepSize = "100 MB"
    sample_metadata: dict[str, Any] = Field(default_factory=dict)
    n_events: int = -1
    offset: int = 0
    triggers: list[str] = Field(default_factory=list)
    object_requirements: dict[str, int] = Field(default_factory=dict)
    keep_branches: list[str] = Field(default_factory=list)

    @field_validator("n_events")
    @classmethod
    def _validate_n_events(cls, value: int) -> int:
        if value < -1:
            raise ValueError("'n_events' must be -1 (all) or >= 0.")
        return value

    @field_validator("offset")
    @classmethod
    def _validate_offset(cls, value: int) -> int:
        if value < 0:
            raise ValueError("'offset' must be >= 0.")
        return value

    @field_validator("input", "output", "tree")
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("string value must not be empty.")
        return stripped

    @field_validator("step_size")
    @classmethod
    def _validate_step_size(cls, value: StepSize) -> StepSize:
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("'step_size' integer value must be > 0.")
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("'step_size' string value must not be empty.")
            return stripped
        raise ValueError("'step_size' must be an integer or string.")

    @field_validator("object_requirements")
    @classmethod
    def _validate_object_requirements(
        cls,
        value: dict[str, int],
    ) -> dict[str, int]:
        for branch_name, min_count in value.items():
            if min_count < 0:
                raise ValueError(f"'object_requirements.{branch_name}' must be >= 0.")
        return value


def _validate_config_object(raw_config: Any) -> SkimConfig:
    """Validate a parsed config object and return `SkimConfig`."""
    try:
        return SkimConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def _load_config(config_path: Path) -> SkimConfig:
    """Load and validate skim configuration JSON from file."""
    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)
    return _validate_config_object(raw_config)


def _load_config_source(config_source: str) -> SkimConfig:
    """Load config from a file path or inline JSON string."""
    config_path = Path(config_source)
    if config_path.exists():
        return _load_config(config_path)

    try:
        raw_config = json.loads(config_source)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Config source is neither an existing file path nor valid JSON string."
        ) from exc
    return _validate_config_object(raw_config)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Skim CMS NanoAOD events from a config file path or inline JSON string."
        )
    )
    parser.add_argument(
        "config_source",
        help="Config file path or inline JSON string",
    )
    return parser.parse_args(argv)


def _first_field_name(arrays: ak.Array) -> str:
    """Return the first field in an awkward record array."""
    if not arrays.fields:
        raise RuntimeError("No fields available in loaded chunk.")
    return cast(str, arrays.fields[0])


def _normalize_step_size(step_size: StepSize) -> StepSize:
    """Convert digit-only step-size strings to entry counts."""
    if isinstance(step_size, int):
        return step_size
    stripped = step_size.strip()
    return int(stripped) if stripped.isdigit() else step_size


def _build_keep_branches(
    keep_branches_cfg: list[str],
    active_object_branches: list[str],
    requested_triggers: list[str],
    all_branches: set[str],
) -> list[str]:
    """Resolve output branches to keep after availability checks."""
    if not keep_branches_cfg:
        keep_branches_cfg = ["run", "luminosityBlock", "event"]
        keep_branches_cfg.extend(active_object_branches)
        keep_branches_cfg.extend(requested_triggers)
        keep_branches_cfg = list(dict.fromkeys(keep_branches_cfg))

    for trigger in requested_triggers:
        if trigger not in keep_branches_cfg:
            keep_branches_cfg.append(trigger)

    requested_trigger_set = set(requested_triggers)
    keep_branches = [
        branch
        for branch in keep_branches_cfg
        if branch in all_branches or branch in requested_trigger_set
    ]
    if not keep_branches:
        raise RuntimeError(
            "No valid branches to keep. Check 'keep_branches' in config."
        )
    return keep_branches


def _coerce_config(config: Union[SkimConfig, Mapping[str, Any]]) -> SkimConfig:
    """Convert a mapping to validated config while allowing direct model input."""
    if isinstance(config, SkimConfig):
        return config
    return SkimConfig.model_validate(dict(config))


def skim_file(
    *,
    input_path: Path,
    config: Union[SkimConfig, Mapping[str, Any]],
    output_path: Path,
    tree_name: str = "Events",
    step_size: StepSize = "100 MB",
) -> dict[str, Any]:
    """Run skimming on one NanoAOD file and return a JSON-serializable report.

    Parameters
    ----------
    input_path:
        Source ROOT file path.
    config:
        `SkimConfig` or mapping accepted by `SkimConfig.model_validate`.
    output_path:
        Destination ROOT path for skimmed events and cutflow histogram.
    tree_name:
        Input tree key, default `Events`.
    step_size:
        uproot iteration chunking (entries or memory-size string).

    Returns
    -------
    dict[str, Any]
        Report object written to `<output>.report.json`.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    validated = _coerce_config(config)
    report_path = output_path.with_suffix(output_path.suffix + ".report.json")

    with uproot.open(input_path) as source:
        if tree_name not in source:
            raise KeyError(f"Tree '{tree_name}' not found in {input_path}")
        tree = source[tree_name]

        total_entries = tree.num_entries
        entry_start = min(validated.offset, total_entries)
        entry_stop = (
            total_entries
            if validated.n_events < 0
            else min(total_entries, entry_start + validated.n_events)
        )

        # Discover available branches once to drive selection and output schema.
        all_branches = set(tree.keys())
        requested_triggers = list(validated.triggers)
        active_triggers = [
            trigger for trigger in requested_triggers if trigger in all_branches
        ]
        missing_triggers = sorted(set(requested_triggers) - set(active_triggers))
        missing_trigger_set = set(missing_triggers)

        object_requirements = dict(validated.object_requirements)
        active_object_branches = [
            branch for branch in object_requirements if branch in all_branches
        ]
        missing_object_branches = sorted(
            set(object_requirements) - set(active_object_branches)
        )

        # Output schema: include requested triggers even if missing in input.
        # Missing triggers are materialized later as all-False boolean branches.
        keep_branches = _build_keep_branches(
            list(validated.keep_branches),
            active_object_branches,
            requested_triggers,
            all_branches,
        )

        # Read only physically available branches from disk.
        # Synthetic missing-trigger branches are injected after selection.
        filter_branches = {branch for branch in keep_branches if branch in all_branches}
        filter_branches.update(active_triggers)
        filter_branches.update(active_object_branches)

        selected_chunks: list[dict[str, ak.Array]] = []
        empty_template: Optional[dict[str, ak.Array]] = None

        cutflow_labels = ["all_events"]
        if requested_triggers:
            cutflow_labels.append("pass_trigger_or")
        for branch in active_object_branches:
            cutflow_labels.append(f"pass_{branch}_ge_{object_requirements[branch]}")
        cutflow_counts = np.zeros(len(cutflow_labels), dtype=np.int64)

        n_scanned = 0
        n_selected = 0

        # Chunked event loop keeps memory usage stable for large files.
        for arrays in tree.iterate(
            filter_name=list(filter_branches),
            entry_start=entry_start,
            entry_stop=entry_stop,
            step_size=step_size,
            library="ak",
        ):
            first_field = _first_field_name(arrays)
            chunk_len = len(arrays[first_field])
            n_scanned += chunk_len

            if empty_template is None:
                empty_template = {}
                for branch in keep_branches:
                    if branch in arrays.fields:
                        empty_template[branch] = arrays[branch][0:0]
                    elif branch in missing_trigger_set:
                        empty_template[branch] = ak.Array(np.zeros(0, dtype=np.bool_))
                    else:
                        raise RuntimeError(
                            f"Branch '{branch}' unavailable to build output template."
                        )

            # Start from all events in this chunk, then apply cuts cumulatively.
            cumulative_mask = np.ones(chunk_len, dtype=np.bool_)
            cutflow_counts[0] += chunk_len

            if requested_triggers:
                trig_mask = np.zeros(chunk_len, dtype=np.bool_)
                for trigger in requested_triggers:
                    # Missing trigger branches contribute False by design.
                    if trigger in arrays.fields:
                        trig_mask |= np.asarray(
                            ak.to_numpy(arrays[trigger]),
                            dtype=np.bool_,
                        )
                cumulative_mask &= trig_mask
                cutflow_counts[1] += int(np.count_nonzero(cumulative_mask))

            stage_index = 2 if requested_triggers else 1
            for branch in active_object_branches:
                min_count = object_requirements[branch]
                branch_values = np.asarray(ak.to_numpy(arrays[branch]), dtype=np.int64)
                cumulative_mask &= branch_values >= min_count
                cutflow_counts[stage_index] += int(np.count_nonzero(cumulative_mask))
                stage_index += 1

            selected_count = int(np.count_nonzero(cumulative_mask))
            chunk_selected: dict[str, ak.Array] = {}
            for branch in keep_branches:
                if branch in arrays.fields:
                    chunk_selected[branch] = arrays[branch][cumulative_mask]
                elif branch in missing_trigger_set:
                    # Keep branch schema stable for downstream consumers.
                    chunk_selected[branch] = ak.Array(
                        np.zeros(selected_count, dtype=np.bool_)
                    )
                else:
                    raise RuntimeError(
                        f"Branch '{branch}' unavailable while writing selected chunk."
                    )

            n_selected += selected_count
            selected_chunks.append(chunk_selected)

        if selected_chunks:
            skimmed = {
                branch: ak.concatenate([chunk[branch] for chunk in selected_chunks])
                for branch in keep_branches
            }
        else:
            skimmed = empty_template if empty_template is not None else {}

    if not skimmed:
        raise RuntimeError("No branches available to write to output.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with uproot.recreate(output_path) as fout:
        fout[tree_name] = skimmed
        cutflow_edges = np.arange(len(cutflow_counts) + 1, dtype=np.float64)
        fout["cutflow"] = (cutflow_counts.astype(np.float64), cutflow_edges)

    report: dict[str, Any] = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "tree": tree_name,
        "input_config": validated.model_dump(),
        "sample_metadata": validated.sample_metadata,
        "requested_event_range": {
            "offset": validated.offset,
            "n_events": validated.n_events,
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
            "counts": [int(value) for value in cutflow_counts],
        },
        "kept_branches": keep_branches,
    }

    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    return report


def run_from_config(config: Union[SkimConfig, Mapping[str, Any]]) -> dict[str, Any]:
    """Run skimming directly from a config object (no config file required)."""
    validated = _coerce_config(config)
    return skim_file(
        input_path=Path(validated.input),
        config=validated,
        output_path=Path(validated.output),
        tree_name=validated.tree,
        step_size=_normalize_step_size(validated.step_size),
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    """CLI entrypoint."""
    args = _parse_args(argv)
    config = _load_config_source(args.config_source)
    output_path = Path(config.output)
    report = run_from_config(config)

    processed = cast(dict[str, Any], report["processed_event_range"])
    n_scanned = int(processed["n_scanned"])
    n_selected = int(processed["n_selected"])
    efficiency = float(processed["selection_efficiency"])

    report_path = output_path.with_suffix(output_path.suffix + ".report.json")
    print(f"Wrote skim: {output_path}")
    print(f"Wrote report: {report_path}")
    print(
        "Scanned events: {0} | Selected events: {1} | Efficiency: {2:.4f}".format(
            n_scanned,
            n_selected,
            efficiency,
        )
    )


if __name__ == "__main__":
    main()
