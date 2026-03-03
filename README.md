# NanoAOD uproot+awkward skimmer

Small Python skimmer for CMS NanoAOD using `uproot` and `awkward`.

## Project layout

- `src/nanoaod_skim/config.py`: config schema and loaders
- `src/nanoaod_skim/skimmer.py`: core skimming engine
- `src/nanoaod_skim/cli.py`: CLI wiring
- `src/nanoaod_skim/runners/`: local/parallel/condor scaffolding helpers
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

```bash
python -m pip install uproot awkward numpy pydantic
```

## Run

```bash
python skim.py config_example.json
```

CLI arguments:

- `config_source` (required positional):
  - path to JSON config file, or
  - inline JSON string.

Inline JSON example:

```bash
python skim.py '{"input":"/path/to/input.root","output":"skim.root","triggers":[],"object_requirements":{},"keep_branches":[]}'
```

Programmatic (no config file) example:

```python
from skim import run_from_config

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

Package-style programmatic import:

```python
from nanoaod_skim import run_from_config
```

## Config notes

- `n_events = -1` means process all events after `offset`.
- `input` and `output` are required in the config.
- `tree` defaults to `Events` and `step_size` defaults to `100 MB`.
- Missing trigger/object branches are reported in the JSON report.
- Missing trigger branches are treated as always `False` in the trigger OR.
- Configured missing trigger branches are written to the skim output as boolean
  branches filled with `False`.
- If `keep_branches` is empty, a minimal default set is used.
- The output ROOT file contains a 1D histogram named `cutflow` with cumulative event
  counts after each selection stage. Bin labels are stored in the report JSON.
- The report JSON includes `input_config` with the fully validated input configuration.

## Validation

```bash
pytest -q
```

```bash
mypy --strict skim.py tests/test_skim.py
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
