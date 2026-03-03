# NanoAOD uproot+awkward skimmer

Small Python skimmer for CMS NanoAOD using `uproot` and `awkward`.

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
