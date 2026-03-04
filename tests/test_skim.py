from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import awkward as ak
import numpy as np
import uproot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skim import _load_config, main, run_from_config, skim_file


def _make_correctionlib_file(path: Path) -> None:
    payload = {
        "schema_version": 2,
        "corrections": [],
        "compound_corrections": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_input_file(path: Path) -> None:
    events: dict[str, Any] = {
        "run": np.array([1, 1, 1, 1, 1, 1], dtype=np.int32),
        "luminosityBlock": np.array([100, 100, 101, 101, 102, 102], dtype=np.int32),
        "event": np.array([10, 11, 12, 13, 14, 15], dtype=np.int64),
        "PV_npvs": np.array([20, 21, 19, 22, 18, 17], dtype=np.int32),
        "HLT_IsoMu24": np.array(
            [True, False, True, False, True, False], dtype=np.bool_
        ),
        "HLT_Ele32_WPTight_Gsf": np.array(
            [False, True, False, False, False, True],
            dtype=np.bool_,
        ),
        "nMuon": np.array([1, 0, 2, 1, 0, 3], dtype=np.int32),
        "nJet": np.array([2, 2, 1, 3, 0, 2], dtype=np.int32),
        "genWeight": np.array([1.0, -1.0, 2.0, 0.5, -0.2, 1.2], dtype=np.float64),
        "Muon_pt": ak.Array([[26.0], [], [28.0, 12.0], [30.0], [], [45.0, 23.0, 10.0]]),
        "Muon_mass": ak.Array(
            [[0.105], [], [0.105, 0.105], [0.105], [], [0.105, 0.105, 0.105]]
        ),
        "Jet_pt": ak.Array(
            [[40.0, 32.0], [50.0, 44.0], [33.0], [60.0, 45.0, 30.0], [], [52.0, 41.0]]
        ),
        "Jet_mass": ak.Array(
            [[10.0, 8.0], [9.0, 7.0], [6.0], [12.0, 10.0, 8.0], [], [11.0, 9.0]]
        ),
    }
    with uproot.recreate(path) as fout:
        fout["Events"] = events


def _base_config() -> dict[str, Any]:
    return {
        "input": "dummy_input.root",
        "output": "dummy_output.root",
        "tree": "Events",
        "step_size": "100 MB",
        "sample_metadata": {
            "sample_name": "TestSample",
            "xsec_pb": 1.23,
            "k_factor": 1.0,
        },
        "n_events": -1,
        "offset": 0,
        "triggers": ["HLT_IsoMu24", "HLT_Ele32_WPTight_Gsf"],
        "object_requirements": {"nMuon": 1, "nJet": 2},
        "keep_branches": [
            "run",
            "luminosityBlock",
            "event",
            "nMuon",
            "nJet",
            "genWeight",
            "HLT_IsoMu24",
            "HLT_Ele32_WPTight_Gsf",
        ],
    }


def test_load_config_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    config_path.write_text(
        json.dumps(
            {
                "input": "input.root",
                "output": "output.root",
                "sample_metadata": {"k_factor": 1.0},
            }
        ),
        encoding="utf-8",
    )
    config = _load_config(config_path)

    assert config.input == "input.root"
    assert config.output == "output.root"
    assert config.n_events == -1
    assert config.offset == 0
    assert config.tree == "Events"
    assert config.step_size == "100 MB"
    assert config.sample_metadata.k_factor == 1.0
    assert config.triggers == []
    assert config.object_requirements == {}
    assert config.keep_branches == []


def test_load_config_validation_errors(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.json"
    config_path.write_text('{"offset": -3}', encoding="utf-8")

    try:
        _load_config(config_path)
    except ValueError as exc:
        assert "offset" in str(exc)
    else:
        raise AssertionError("Expected ValueError for negative offset")


def test_load_config_requires_input_output(tmp_path: Path) -> None:
    config_path = tmp_path / "bad_missing_required.json"
    config_path.write_text("{}", encoding="utf-8")

    try:
        _load_config(config_path)
    except ValueError as exc:
        assert "input" in str(exc)
        assert "output" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing required fields")


def test_load_config_requires_k_factor(tmp_path: Path) -> None:
    config_path = tmp_path / "bad_missing_k_factor.json"
    config_path.write_text(
        json.dumps(
            {
                "input": "input.root",
                "output": "output.root",
                "sample_metadata": {"xsec_pb": 1.23},
            }
        ),
        encoding="utf-8",
    )

    try:
        _load_config(config_path)
    except ValueError as exc:
        assert "k_factor" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing k_factor")


def test_load_config_accepts_correctionlib_files(tmp_path: Path) -> None:
    cset_path = tmp_path / "corr.json"
    _make_correctionlib_file(cset_path)
    config_path = tmp_path / "cfg_with_cset.json"
    config_path.write_text(
        json.dumps(
            {
                "input": "input.root",
                "output": "output.root",
                "sample_metadata": {"k_factor": 1.0},
                "correctionlib_files": [str(cset_path)],
            }
        ),
        encoding="utf-8",
    )

    config = _load_config(config_path)
    assert config.correctionlib_files == [str(cset_path)]


def test_load_config_accepts_multiple_event_weight_corrections(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg_event_weight_corrections.json"
    config = _base_config()
    config["event_weight_corrections"] = [
        {
            "weight_branch": "genWeight",
            "suffix": "_sfA",
            "variations": ["nominal", "varA"],
        },
        {
            "weight_branch": "genWeight",
            "suffix": "_sfB",
            "variations": ["nominal", "varB"],
        },
    ]
    config_path.write_text(json.dumps(config), encoding="utf-8")

    loaded = _load_config(config_path)
    assert len(loaded.event_weight_corrections) == 2


def test_skim_file_selection_and_cutflow(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    report = skim_file(
        input_path=input_path,
        config=_base_config(),
        output_path=output_path,
        step_size=2,
    )

    assert report["processed_event_range"]["n_scanned"] == 6
    assert report["processed_event_range"]["n_selected"] == 2
    assert report["cutflow"]["labels"] == [
        "all_events",
        "pass_trigger_or",
        "pass_nMuon_ge_1",
        "pass_nJet_ge_2",
    ]
    assert report["cutflow"]["counts"] == [6, 5, 3, 2]

    with uproot.open(output_path) as fin:
        tree = fin["Events"]
        assert tree.num_entries == 2
        events = tree.arrays(["event"], library="np")
        assert events["event"].tolist() == [10, 15]

        cutflow = fin["cutflow"].to_numpy()
        assert cutflow[0].tolist() == [6.0, 5.0, 3.0, 2.0]


def test_skim_file_offset_and_n_events(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["offset"] = 1
    config["n_events"] = 3
    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
    )

    assert report["processed_event_range"]["entry_start"] == 1
    assert report["processed_event_range"]["entry_stop"] == 4
    assert report["processed_event_range"]["n_scanned"] == 3
    assert report["processed_event_range"]["n_selected"] == 0
    assert report["cutflow"]["counts"] == [3, 2, 1, 0]


def test_missing_branches_are_reported(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["triggers"] = ["HLT_IsoMu24", "HLT_DoesNotExist"]
    config["object_requirements"] = {"nMuon": 1, "nTau": 1}

    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
    )

    assert report["selection"]["active_triggers"] == ["HLT_IsoMu24"]
    assert report["selection"]["missing_triggers"] == ["HLT_DoesNotExist"]
    assert report["selection"]["missing_triggers_default_false"] is True
    assert report["selection"]["missing_object_branches"] == ["nTau"]

    with uproot.open(output_path) as fin:
        tree = fin["Events"]
        arrays = tree.arrays(["HLT_DoesNotExist"], library="np")
        values = arrays["HLT_DoesNotExist"]
        assert values.dtype == np.bool_
        assert values.tolist() == [False, False]


def test_all_missing_triggers_default_to_false(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["triggers"] = ["HLT_Missing1", "HLT_Missing2"]

    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
        step_size=3,
    )

    assert report["selection"]["active_triggers"] == []
    assert report["selection"]["missing_triggers"] == ["HLT_Missing1", "HLT_Missing2"]
    assert report["processed_event_range"]["n_selected"] == 0
    assert report["cutflow"]["counts"][1] == 0

    with uproot.open(output_path) as fin:
        tree = fin["Events"]
        assert tree.num_entries == 0
        arrays = tree.arrays(["HLT_Missing1", "HLT_Missing2"], library="np")
        assert arrays["HLT_Missing1"].dtype == np.bool_
        assert arrays["HLT_Missing2"].dtype == np.bool_


def test_missing_non_trigger_keep_branch_is_dropped(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["keep_branches"] = ["event", "Branch_DoesNotExist"]

    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
    )

    assert "event" in report["kept_branches"]
    assert "Branch_DoesNotExist" not in report["kept_branches"]

    with uproot.open(output_path) as fin:
        tree = fin["Events"]
        keys = tree.keys()
        assert "event" in keys
        assert "Branch_DoesNotExist" not in keys


def test_corrections_append_pt_mass_and_event_weight_variations(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["energy_corrections"] = [
        {
            "pt_branch": "Muon_pt",
            "mass_branch": "Muon_mass",
            "suffix": "_calib",
            "variations": ["nominal", "jerA", "jerB"],
        }
    ]
    config["event_weight_correction"] = {
        "weight_branch": "genWeight",
        "suffix": "_sf",
        "variations": ["nominal", "pileupUp"],
    }
    config["keep_branches"] = [
        "event",
        "Muon_pt",
        "Muon_mass",
        "genWeight",
        "HLT_IsoMu24",
        "HLT_Ele32_WPTight_Gsf",
        "nMuon",
        "nJet",
    ]

    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
    )

    expected_branches = {
        "Muon_pt_calib_nominal",
        "Muon_mass_calib_nominal",
        "Muon_pt_calib_jerA",
        "Muon_mass_calib_jerA",
        "Muon_pt_calib_jerB",
        "Muon_mass_calib_jerB",
        "genWeight_sf_nominal",
        "genWeight_sf_pileupUp",
    }

    assert expected_branches.issubset(set(report["corrections"]["output_branches"]))

    with uproot.open(output_path) as fin:
        tree = fin["Events"]
        keys = set(tree.keys())
        assert expected_branches.issubset(keys)

        arrays = tree.arrays(
            [
                "Muon_pt",
                "Muon_pt_calib_nominal",
                "Muon_pt_calib_jerA",
                "Muon_mass",
                "Muon_mass_calib_nominal",
                "genWeight",
                "genWeight_sf_nominal",
                "genWeight_sf_pileupUp",
            ],
            library="ak",
        )
        assert ak.to_list(arrays["Muon_pt_calib_nominal"]) == ak.to_list(
            arrays["Muon_pt"]
        )
        assert ak.to_list(arrays["Muon_pt_calib_jerA"]) == ak.to_list(arrays["Muon_pt"])
        assert ak.to_list(arrays["Muon_mass_calib_nominal"]) == ak.to_list(
            arrays["Muon_mass"]
        )
        assert ak.to_list(arrays["genWeight_sf_nominal"]) == ak.to_list(
            arrays["genWeight"]
        )
        assert ak.to_list(arrays["genWeight_sf_pileupUp"]) == ak.to_list(
            arrays["genWeight"]
        )

    assert report["corrections"]["mock_mode"] is True
    assert report["corrections"]["event_weight_correction"]["suffix"] == "_sf"


def test_load_config_rejects_empty_correction_variations(tmp_path: Path) -> None:
    config_path = tmp_path / "bad_empty_variations.json"
    config = _base_config()
    config["energy_corrections"] = [
        {
            "pt_branch": "Muon_pt",
            "mass_branch": "Muon_mass",
            "suffix": "_calib",
            "variations": [],
        }
    ]
    config_path.write_text(json.dumps(config), encoding="utf-8")

    try:
        _load_config(config_path)
    except ValueError as exc:
        assert "variations" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty correction variations")


def test_missing_correction_input_branch_raises_runtime_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["energy_corrections"] = [
        {
            "pt_branch": "Muon_pt",
            "mass_branch": "Muon_mass_missing",
            "suffix": "_calib",
            "variations": ["nominal"],
        }
    ]

    try:
        skim_file(
            input_path=input_path,
            config=config,
            output_path=output_path,
        )
    except RuntimeError as exc:
        assert "Missing correction input branch" in str(exc)
        assert "Muon_mass_missing" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing correction input")


def test_missing_event_weight_input_branch_raises_runtime_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["event_weight_correction"] = {
        "weight_branch": "genWeightMissing",
        "suffix": "_sf",
        "variations": ["nominal", "altA"],
    }

    try:
        skim_file(
            input_path=input_path,
            config=config,
            output_path=output_path,
        )
    except RuntimeError as exc:
        assert "Missing correction input branch" in str(exc)
        assert "genWeightMissing" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing event weight input")


def test_missing_correctionlib_file_raises_file_not_found(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["correctionlib_files"] = [str(tmp_path / "does_not_exist.json")]

    try:
        skim_file(
            input_path=input_path,
            config=config,
            output_path=output_path,
        )
    except FileNotFoundError as exc:
        assert "Correctionlib file not found" in str(exc)
    else:
        raise AssertionError(
            "Expected FileNotFoundError for missing correctionlib file"
        )


def test_correctionlib_files_are_reported(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    cset_path = tmp_path / "corr.json"
    _make_input_file(input_path)
    _make_correctionlib_file(cset_path)

    config = _base_config()
    config["correctionlib_files"] = [str(cset_path)]

    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
    )

    assert report["corrections"]["correctionlib_files"] == [str(cset_path)]


def test_multiple_corrections_for_different_objects(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    cset_path = tmp_path / "corr.json"
    _make_input_file(input_path)
    _make_correctionlib_file(cset_path)

    config = _base_config()
    config["correctionlib_files"] = [str(cset_path)]
    config["energy_corrections"] = [
        {
            "method": "scale_pt_mass",
            "pt_branch": "Muon_pt",
            "mass_branch": "Muon_mass",
            "suffix": "_muCalib",
            "variations": ["nominal", "muVarA"],
            "correction_file": str(cset_path),
            "correction_name": "muon_scale",
            "inputs": {"pt": "Muon_pt"},
        },
        {
            "method": "scale_pt_mass",
            "pt_branch": "Jet_pt",
            "mass_branch": "Jet_mass",
            "suffix": "_jetCalib",
            "variations": ["nominal", "jetVarA"],
            "correction_file": str(cset_path),
            "correction_name": "jet_scale",
            "inputs": {"pt": "Jet_pt"},
        },
    ]
    config["event_weight_corrections"] = [
        {
            "method": "event_weight_sf",
            "weight_branch": "genWeight",
            "suffix": "_sfA",
            "variations": ["nominal", "sfVarA"],
            "correction_file": str(cset_path),
            "correction_name": "pu_sf",
            "inputs": {"nPU": "PV_npvs"},
        },
        {
            "method": "event_weight_sf",
            "weight_branch": "genWeight",
            "suffix": "_sfB",
            "variations": ["nominal", "sfVarB"],
            "correction_file": str(cset_path),
            "correction_name": "btag_sf",
            "inputs": {"ht": "nJet"},
        },
    ]
    config["keep_branches"] = [
        "event",
        "Muon_pt",
        "Muon_mass",
        "Jet_pt",
        "Jet_mass",
        "genWeight",
        "HLT_IsoMu24",
        "HLT_Ele32_WPTight_Gsf",
        "nMuon",
        "nJet",
    ]

    report = skim_file(
        input_path=input_path,
        config=config,
        output_path=output_path,
    )

    assert "Muon_pt_muCalib_muVarA" in report["corrections"]["output_branches"]
    assert "Jet_mass_jetCalib_jetVarA" in report["corrections"]["output_branches"]
    assert "genWeight_sfA_sfVarA" in report["corrections"]["output_branches"]
    assert "genWeight_sfB_sfVarB" in report["corrections"]["output_branches"]
    assert len(report["corrections"]["event_weight_corrections"]) == 2


def test_unknown_correction_method_raises_runtime_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["energy_corrections"] = [
        {
            "method": "unknown_method",
            "pt_branch": "Muon_pt",
            "mass_branch": "Muon_mass",
            "suffix": "_x",
            "variations": ["nominal"],
        }
    ]

    try:
        skim_file(
            input_path=input_path,
            config=config,
            output_path=output_path,
        )
    except RuntimeError as exc:
        assert "Unknown energy correction method" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for unknown correction method")


def test_correction_file_not_loaded_raises_runtime_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    _make_input_file(input_path)

    config = _base_config()
    config["energy_corrections"] = [
        {
            "method": "scale_pt_mass",
            "pt_branch": "Muon_pt",
            "mass_branch": "Muon_mass",
            "suffix": "_x",
            "variations": ["nominal"],
            "correction_file": "/tmp/not_loaded.json",
        }
    ]

    try:
        skim_file(
            input_path=input_path,
            config=config,
            output_path=output_path,
        )
    except RuntimeError as exc:
        assert "correction_file is not loaded" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for unloaded correction_file")


def test_main_writes_report_json(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim.root"
    config_path = tmp_path / "config.json"
    _make_input_file(input_path)
    config = _base_config()
    config["input"] = str(input_path)
    config["output"] = str(output_path)
    config["step_size"] = 2
    config_path.write_text(json.dumps(config), encoding="utf-8")

    main(["skim", str(config_path)])

    report_path = tmp_path / "skim.root.report.json"
    assert report_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["processed_event_range"]["n_selected"] == 2


def test_main_accepts_inline_json_config(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim_inline.root"
    _make_input_file(input_path)

    config = _base_config()
    config["input"] = str(input_path)
    config["output"] = str(output_path)
    config["step_size"] = 2

    main(["skim", json.dumps(config)])

    report_path = tmp_path / "skim_inline.root.report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["input_config"]["input"] == str(input_path)


def test_run_from_config_without_file(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    output_path = tmp_path / "skim_programmatic.root"
    _make_input_file(input_path)

    config = _base_config()
    config["input"] = str(input_path)
    config["output"] = str(output_path)
    config["step_size"] = 2

    report = run_from_config(config)
    assert report["processed_event_range"]["n_selected"] == 2
    assert report["input_config"]["output"] == str(output_path)


def test_main_rejects_invalid_config_source() -> None:
    try:
        main(["skim", "{not valid json"])
    except ValueError as exc:
        assert "neither an existing file path nor valid JSON" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid config source")


def test_missing_tree_raises_key_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.root"
    with uproot.recreate(input_path) as fout:
        fout["OtherTree"] = {"x": np.array([1, 2, 3], dtype=np.int32)}

    try:
        skim_file(
            input_path=input_path,
            config=_base_config(),
            output_path=tmp_path / "skim.root",
            tree_name="Events",
        )
    except KeyError as exc:
        assert "Events" in str(exc)
    else:
        raise AssertionError("Expected KeyError for missing tree")
