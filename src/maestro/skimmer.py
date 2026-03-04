from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union, cast

import awkward as ak
import correctionlib
import numpy as np
import uproot

from .chunking import StepSize, compute_entry_range, normalize_step_size
from .config import (
    EnergyCorrectionConfig,
    EventWeightCorrectionConfig,
    SkimConfig,
    coerce_config,
)
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


def _build_corrected_branch_name(
    *,
    base_branch: str,
    suffix: str,
    variation: str,
) -> str:
    return f"{base_branch}{suffix}_{variation}"


def _apply_energy_correction_mock(
    *,
    inputs: Mapping[str, ak.Array],
    correction_cfg: EnergyCorrectionConfig,
    variation: str,
    correction_set: Optional[Any],
) -> dict[str, ak.Array]:
    _ = correction_cfg
    _ = variation
    _ = correction_set
    corrected: dict[str, ak.Array] = {}
    for branch in correction_cfg.corrected_branches:
        if branch not in inputs:
            raise RuntimeError(
                "Corrected branch is missing from correction inputs: "
                f"{branch}. Add it to 'input_branches'."
            )
        corrected[branch] = inputs[branch]
    return corrected


def _apply_event_weight_scale_factor_mock(
    *,
    inputs: Mapping[str, ak.Array],
    correction_cfg: EventWeightCorrectionConfig,
    variation: str,
    correction_set: Optional[Any],
) -> ak.Array:
    _ = correction_cfg
    _ = variation
    _ = correction_set
    return inputs[correction_cfg.weight_branch]


ENERGY_CORRECTION_METHODS = {
    "scale_pt_mass": _apply_energy_correction_mock,
}


EVENT_WEIGHT_CORRECTION_METHODS = {
    "event_weight_sf": _apply_event_weight_scale_factor_mock,
}


def _load_correctionlib_sets(correctionlib_files: list[str]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for file_path in correctionlib_files:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Correctionlib file not found: {path}")
        cset = correctionlib.CorrectionSet.from_file(str(path))
        loaded[str(path)] = cset
        loaded[str(path.resolve())] = cset
    return loaded


def _resolve_correction_set(
    *,
    correction_file: Optional[str],
    correctionlib_sets: Mapping[str, Any],
) -> Optional[Any]:
    if correction_file is None:
        return None
    path = Path(correction_file)
    if correction_file in correctionlib_sets:
        return correctionlib_sets[correction_file]
    resolved_key = str(path.resolve())
    if resolved_key in correctionlib_sets:
        return correctionlib_sets[resolved_key]
    raise RuntimeError(
        "Configured correction_file is not loaded via 'correctionlib_files': "
        f"{correction_file}"
    )


def _require_correction_inputs(
    *,
    all_branches: set[str],
    energy_corrections: list[EnergyCorrectionConfig],
    event_weight_corrections: list[EventWeightCorrectionConfig],
) -> None:
    for correction in energy_corrections:
        for branch in correction.input_branches:
            if branch not in all_branches:
                raise RuntimeError(
                    "Missing correction input branch: "
                    f"{branch} (energy correction input_branches)"
                )
    for event_weight_correction in event_weight_corrections:
        for branch in event_weight_correction.input_branches:
            if branch not in all_branches:
                raise RuntimeError(
                    "Missing correction input branch: "
                    f"{branch} (event_weight_correction.input_branches)"
                )


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
    correctionlib_sets = _load_correctionlib_sets(validated.correctionlib_files)

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
        energy_corrections = list(validated.energy_corrections)
        event_weight_corrections = list(validated.event_weight_corrections)
        _require_correction_inputs(
            all_branches=all_branches,
            energy_corrections=energy_corrections,
            event_weight_corrections=event_weight_corrections,
        )
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
        for correction in energy_corrections:
            filter_branches.update(correction.input_branches)
        for event_weight_correction in event_weight_corrections:
            filter_branches.update(event_weight_correction.input_branches)

        selected_chunks: list[dict[str, ak.Array]] = []
        empty_template: Optional[dict[str, ak.Array]] = None

        cutflow_labels = ["all_events"]
        if requested_triggers:
            cutflow_labels.append("pass_trigger_or")
        for branch in active_object_branches:
            cutflow_labels.append(f"pass_{branch}_ge_{object_requirements[branch]}")
        cutflow_counts = np.zeros(len(cutflow_labels), dtype=np.int64)
        corrected_output_branches: list[str] = []

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

            for correction in energy_corrections:
                energy_handler = ENERGY_CORRECTION_METHODS.get(correction.method)
                if energy_handler is None:
                    raise RuntimeError(
                        f"Unknown energy correction method: {correction.method}"
                    )
                correction_set = _resolve_correction_set(
                    correction_file=correction.correction_file,
                    correctionlib_sets=correctionlib_sets,
                )
                correction_inputs = {
                    branch: arrays[branch][cumulative_mask]
                    for branch in correction.input_branches
                }
                for variation in correction.variations:
                    corrected_values = energy_handler(
                        inputs=correction_inputs,
                        correction_cfg=correction,
                        variation=variation,
                        correction_set=correction_set,
                    )
                    for base_branch in correction.corrected_branches:
                        if base_branch not in corrected_values:
                            raise RuntimeError(
                                "Energy correction output missing corrected branch: "
                                f"{base_branch}"
                            )
                        out_name = _build_corrected_branch_name(
                            base_branch=base_branch,
                            suffix=correction.suffix,
                            variation=variation,
                        )
                        chunk_selected[out_name] = corrected_values[base_branch]
                        if out_name not in corrected_output_branches:
                            corrected_output_branches.append(out_name)

            for event_weight_correction in event_weight_corrections:
                event_handler = EVENT_WEIGHT_CORRECTION_METHODS.get(
                    event_weight_correction.method
                )
                if event_handler is None:
                    raise RuntimeError(
                        "Unknown event weight correction method: "
                        f"{event_weight_correction.method}"
                    )
                correction_set = _resolve_correction_set(
                    correction_file=event_weight_correction.correction_file,
                    correctionlib_sets=correctionlib_sets,
                )
                correction_inputs = {
                    branch: arrays[branch][cumulative_mask]
                    for branch in event_weight_correction.input_branches
                }
                for variation in event_weight_correction.variations:
                    corrected_weight = event_handler(
                        inputs=correction_inputs,
                        correction_cfg=event_weight_correction,
                        variation=variation,
                        correction_set=correction_set,
                    )
                    weight_name = _build_corrected_branch_name(
                        base_branch=event_weight_correction.weight_branch,
                        suffix=event_weight_correction.suffix,
                        variation=variation,
                    )
                    chunk_selected[weight_name] = corrected_weight
                    if weight_name not in corrected_output_branches:
                        corrected_output_branches.append(weight_name)

            n_selected += selected_count
            selected_chunks.append(chunk_selected)

        if selected_chunks:
            skimmed = {
                branch: ak.concatenate([chunk[branch] for chunk in selected_chunks])
                for branch in selected_chunks[0]
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
        sample_metadata=validated.sample_metadata.model_dump(),
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
        corrections={
            "energy_corrections": [item.model_dump() for item in energy_corrections],
            "event_weight_corrections": [
                item.model_dump() for item in event_weight_corrections
            ],
            "correctionlib_files": validated.correctionlib_files,
            "output_branches": corrected_output_branches,
            "mock_mode": True,
        },
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
