from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union, cast

import awkward as ak
import numpy as np
import uproot

from .chunking import StepSize, compute_entry_range, normalize_step_size
from .config import SkimConfig, coerce_config
from .report import build_report


def _first_field_name(arrays: ak.Array) -> str:
    if not arrays.fields:
        raise RuntimeError("No fields available in loaded chunk.")
    return cast(str, arrays.fields[0])


def _build_keep_branches(
    keep_branches_cfg: list[str],
    active_object_branches: list[str],
    requested_triggers: list[str],
    all_branches: set[str],
) -> list[str]:
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


def skim_file(
    *,
    input_path: Path,
    config: Union[SkimConfig, Mapping[str, Any]],
    output_path: Path,
    tree_name: str = "Events",
    step_size: StepSize = "100 MB",
) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    validated = coerce_config(config)
    report_path = output_path.with_suffix(output_path.suffix + ".report.json")

    with uproot.open(input_path) as source:
        if tree_name not in source:
            raise KeyError(f"Tree '{tree_name}' not found in {input_path}")
        tree = source[tree_name]

        total_entries = tree.num_entries
        entry_start, entry_stop = compute_entry_range(
            total_entries,
            offset=validated.offset,
            n_events=validated.n_events,
        )

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

        keep_branches = _build_keep_branches(
            list(validated.keep_branches),
            active_object_branches,
            requested_triggers,
            all_branches,
        )

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

            cumulative_mask = np.ones(chunk_len, dtype=np.bool_)
            cutflow_counts[0] += chunk_len

            if requested_triggers:
                trig_mask = np.zeros(chunk_len, dtype=np.bool_)
                for trigger in requested_triggers:
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

    report = build_report(
        input_file=str(input_path),
        output_file=str(output_path),
        tree=tree_name,
        input_config=validated.model_dump(),
        sample_metadata=validated.sample_metadata,
        offset=validated.offset,
        n_events=validated.n_events,
        entry_start=entry_start,
        entry_stop=entry_stop,
        n_scanned=n_scanned,
        n_selected=n_selected,
        requested_triggers=requested_triggers,
        active_triggers=active_triggers,
        missing_triggers=missing_triggers,
        object_requirements=object_requirements,
        missing_object_branches=missing_object_branches,
        cutflow_labels=cutflow_labels,
        cutflow_counts=[int(value) for value in cutflow_counts],
        kept_branches=keep_branches,
    )

    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    return report


def run_from_config(config: Union[SkimConfig, Mapping[str, Any]]) -> dict[str, Any]:
    validated = coerce_config(config)
    return skim_file(
        input_path=Path(validated.input),
        config=validated,
        output_path=Path(validated.output),
        tree_name=validated.tree,
        step_size=normalize_step_size(validated.step_size),
    )
