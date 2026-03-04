# Maestro

Maestro is an orchestrator for common CMS NanoAOD analysis workflows.
It includes a Python skimmer implementation using `uproot` and `awkward`.
This tool was built with support from AI coding agents.

## Acknowledgments

Development used AI-assisted coding workflows with human oversight for design
choices, validation, and final review.

## Project layout

- `src/maestro/config.py`: config schema and loaders
- `src/maestro/skimmer.py`: core skimming engine
- `src/maestro/cli.py`: CLI wiring
- `src/maestro/runners/`: local/parallel/condor scaffolding helpers
- `scripts/`: operational helper scripts (`make_tasks.py`, `merge_outputs.py`)
- `workflows/`: execution templates for GNU Parallel and HTCondor

## What it does

- Reads one NanoAOD ROOT input file.
- Reads a JSON config with:
  - MC sample metadata
  - number of events to process (`n_events`)
  - starting event offset (`offset`)
  - trigger list (`triggers`)
  - object counting cuts (`object_requirements`)
  - output branches (`keep_branches`)
- Applies event selection:
  - OR of configured trigger paths
  - minimum object counts (for example `nMuon >= 1`, `nJet >= 2`)
- Writes skimmed ROOT output, a `cutflow` histogram, and a JSON report.

## Install

Create a local virtual environment and install runtime dependencies:

```bash
bash scripts/install.sh
```

Install Maestro in editable mode to expose the `maestro` CLI command:

```bash
.venv/bin/python -m pip install -e .
```

Install dev dependencies (tests, mypy, ruff):

```bash
bash scripts/install.sh --dev
```

Manual equivalent:

```bash
python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

## Run

`maestro` uses Typer subcommands. Current command: `skim`.

```bash
maestro skim config_example.json
```

CLI arguments:

- `config_source` (required positional):
  - path to JSON config file, or
  - inline JSON string.

Inline JSON example:

```bash
maestro skim '{"input":"/path/to/input.root","output":"skim.root","sample_metadata":{"k_factor":1.0},"triggers":[],"object_requirements":{},"keep_branches":[]}'
```

Programmatic (no config file) example:

```python
from maestro import run_from_config

report = run_from_config(
    {
        "input": "/path/to/input.root",
        "output": "skim.root",
        "triggers": [],
        "object_requirements": {},
        "keep_branches": [],
    }
)
```

## Config notes

- `n_events = -1` means process all events after `offset`.
- `input` and `output` are required in the config.
- `sample_metadata.k_factor` is required and must be > 0.
- `tree` defaults to `Events` and `step_size` defaults to `100 MB`.
- `correctionlib_files` is an optional list of correctionlib JSON files to load.
- `energy_corrections` allows mocked object-energy corrections for pT and mass.
- `event_weight_correction` supports one mocked event-wise scale factor block.
- `event_weight_corrections` supports multiple event-wise scale factor blocks.
- Correction output branch names are `<input_branch><suffix>_<variation>`.
- Variations are user-defined strings (not limited to up/down).
- If a configured correction input branch is missing, execution fails immediately.
- If a configured correctionlib file is missing, execution fails immediately.
- Missing trigger/object branches are reported in the JSON report.
- Missing trigger branches are treated as always `False` in the trigger OR.
- Configured missing trigger branches are written to the skim output as boolean
  branches filled with `False`.
- If `keep_branches` is empty, a minimal default set is used.
- The output ROOT file contains a 1D histogram named `cutflow` with cumulative event
  counts after each selection stage. Bin labels are stored in the report JSON.
- The report JSON includes `input_config` with the fully validated input configuration.

### Correction config example

```json
{
  "correctionlib_files": ["/path/to/corrections.json"],
  "energy_corrections": [
    {
      "pt_branch": "Muon_pt",
      "mass_branch": "Muon_mass",
      "suffix": "_calib",
      "variations": ["nominal", "jerA", "jerB"]
    }
  ],
  "event_weight_correction": {
    "weight_branch": "genWeight",
    "suffix": "_sf",
    "variations": ["nominal", "pileupUp"]
  }
}
```

### Multiple corrections example

```json
{
  "correctionlib_files": ["/path/to/corrections.json"],
  "energy_corrections": [
    {
      "method": "scale_pt_mass",
      "pt_branch": "Muon_pt",
      "mass_branch": "Muon_mass",
      "suffix": "_muCalib",
      "variations": ["nominal", "muVarA"],
      "correction_file": "/path/to/corrections.json",
      "correction_name": "muon_scale"
    },
    {
      "method": "scale_pt_mass",
      "pt_branch": "Jet_pt",
      "mass_branch": "Jet_mass",
      "suffix": "_jetCalib",
      "variations": ["nominal", "jetVarA"],
      "correction_file": "/path/to/corrections.json",
      "correction_name": "jet_scale"
    }
  ],
  "event_weight_corrections": [
    {
      "method": "event_weight_sf",
      "weight_branch": "genWeight",
      "suffix": "_sfA",
      "variations": ["nominal", "sfVarA"],
      "correction_file": "/path/to/corrections.json",
      "correction_name": "pu_sf"
    },
    {
      "method": "event_weight_sf",
      "weight_branch": "genWeight",
      "suffix": "_sfB",
      "variations": ["nominal", "sfVarB"],
      "correction_file": "/path/to/corrections.json",
      "correction_name": "btag_sf"
    }
  ]
}
```

Current implementation uses mock correction functions (pass-through), so values
are unchanged until you replace the mock functions in `src/maestro/skimmer.py`.

### Implementing real corrections

Replace the mock hooks in `src/maestro/skimmer.py`:

- `_apply_energy_correction_mock(...)`
- `_apply_event_weight_scale_factor_mock(...)`

Recommended handling for object energy corrections:

- Use `variation` to switch correction scenario (for example `nominal`, `jerA`,
  `jesAbsolute`, custom analysis names).
- Return corrected pT and mass with the same event/object structure as input.
- Keep output jagged dimensions identical to the source object branches.
- Keep behavior deterministic for reproducibility.

Recommended handling for event-wise scale factors:

- Read event-level weight from `event_weight_correction.weight_branch`.
- Apply multiplicative scale factors per event for each configured variation.
- Return one value per selected event, preserving event order.

Runtime contract:

- All configured `correctionlib_files` are loaded at startup.
- Missing correction input branches cause immediate failure (`RuntimeError`).
- Missing correctionlib files cause immediate failure (`FileNotFoundError`).
- Output branch naming is fixed as `<base><suffix>_<variation>`.
- All configured variations are materialized in the output tree and listed in the
  report `corrections.output_branches` section.

## Validation

```bash
pytest -q
```

```bash
mypy --strict skim.py src/maestro/*.py src/maestro/runners/*.py scripts/*.py tests/test_skim.py
```

## Distributed execution scaffolding

- GNU Parallel template: `workflows/gnu_parallel/`
- HTCondor template: `workflows/htcondor/`
These are templates to bootstrap large-scale production workflows; adapt site
and campaign details before production use.

### `make_tasks.py` usage

`scripts/make_tasks.py` converts a JSON manifest (array of config objects) into a
GNU Parallel task file.

```bash
python scripts/make_tasks.py \
  --manifest /path/to/manifest.json \
  --output workflows/gnu_parallel/tasks.txt
```

Manifest format example:

```json
[
  {
    "input": "/data/input_1.root",
    "output": "out/skim_1.root",
    "triggers": ["HLT_IsoMu24"],
    "object_requirements": {"nMuon": 1},
    "keep_branches": ["event", "nMuon"]
  },
  {
    "input": "/data/input_2.root",
    "output": "out/skim_2.root",
    "triggers": ["HLT_IsoMu24"],
    "object_requirements": {"nMuon": 1},
    "keep_branches": ["event", "nMuon"]
  }
]
```

### GNU Parallel

Use the provided runner script (includes progress bar via GNU Parallel default bar):

```bash
bash workflows/gnu_parallel/run.sh workflows/gnu_parallel/tasks.txt 8
```

Equivalent direct command:

```bash
parallel --bar --jobs 8 < workflows/gnu_parallel/tasks.txt
```

### HTCondor

1) Prepare your config source (file path or inline JSON argument strategy).

2) Use or adapt `workflows/htcondor/submit.sub` and `workflows/htcondor/run_job.sh`.

3) Submit:

```bash
condor_submit workflows/htcondor/submit.sub
```

The template currently passes `config_example.json` as job argument; change
`arguments` in `submit.sub` to your per-job config source.
