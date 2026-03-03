# AGENTS.md

Operating guide for agentic coding tools in this repository.

## Project Summary

- Language: Python
- Domain: CMS NanoAOD skimming with `uproot` + `awkward`
- Compatibility entrypoint: `skim.py`
- Package source: `src/maestro/`
- Tests: `tests/test_skim.py`
- Example config: `config_example.json`
- Workflow templates: `workflows/gnu_parallel/`, `workflows/htcondor/`

## Cursor / Copilot Rules

Checked locations requested by user:

- `.cursor/rules/`: not present
- `.cursorrules`: not present
- `.github/copilot-instructions.md`: not present

No extra Cursor/Copilot instruction files are active.

## Environment Setup

Preferred setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Without activation:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Build / Lint / Type / Test

No package build step exists; use checks below as the quality gate.

### Syntax check

```bash
.venv/bin/python -m py_compile skim.py src/maestro/*.py src/maestro/runners/*.py scripts/*.py tests/test_skim.py
```

### Lint

```bash
.venv/bin/ruff check .
```

### Format

```bash
.venv/bin/ruff format .
```

### Type check (strict)

```bash
.venv/bin/mypy --strict skim.py src/maestro/*.py src/maestro/runners/*.py scripts/*.py tests/test_skim.py
```

### Run full test suite

```bash
.venv/bin/pytest -q
```

### Run a single test file

```bash
.venv/bin/pytest -q tests/test_skim.py
```

### Run a single test function

```bash
.venv/bin/pytest -q tests/test_skim.py::test_skim_file_selection_and_cutflow
```

### Run tests by keyword

```bash
.venv/bin/pytest -q -k cutflow
```

## Runtime Usage

CLI uses Typer with subcommands; current command is `skim`.

- File config:

```bash
maestro skim config_example.json
```

- Inline JSON config:

```bash
maestro skim '{"input":"/path/to/in.root","output":"skim.root","sample_metadata":{"k_factor":1.0},"triggers":[],"object_requirements":{},"keep_branches":[]}'
```

- Programmatic usage (preferred in Python code):

```python
from maestro import run_from_config

report = run_from_config({...})
```

Expected artifacts:

- Output ROOT with skimmed `Events`
- `cutflow` histogram in output ROOT
- Report JSON at `<output>.report.json`

## Distributed Execution

- GNU Parallel task generation:

```bash
.venv/bin/python scripts/make_tasks.py --manifest /path/to/manifest.json --output workflows/gnu_parallel/tasks.txt
```

- GNU Parallel execution (with progress bar):

```bash
bash workflows/gnu_parallel/run.sh workflows/gnu_parallel/tasks.txt 8
```

- HTCondor template submit:

```bash
condor_submit workflows/htcondor/submit.sub
```

## Code Style Guidelines

Follow established patterns in `src/maestro/` and existing tests.

### Imports

- Group imports: stdlib, third-party, local.
- Keep imports explicit; avoid wildcard imports.
- Keep ordering stable and readable.

### Formatting

- Follow PEP 8 and Black-compatible style.
- Prefer readability over dense one-liners.
- Use trailing commas for multiline literals/calls.

### Types

- Add type annotations to all new/modified functions.
- Keep strict mypy passing.
- Prefer concrete generics (`list[str]`, `dict[str, int]`, etc.).
- Use structured models (`pydantic.BaseModel`, `TypedDict`) for schema-like data.
- Keep `Any` usage local and intentional.

### Naming

- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Tests: `test_<behavior>`

### Error Handling

- Validate user/config inputs early.
- Raise specific exceptions (`ValueError`, `KeyError`, `FileNotFoundError`, `RuntimeError`).
- Include path/key/value context in errors.
- Do not swallow exceptions silently.

### Analysis Semantics

- Keep selection logic explicit and auditable.
- Preserve cumulative cutflow semantics.
- Trigger logic is OR over requested triggers.
- Missing trigger branches are treated as always `False`.
- Missing configured trigger branches are materialized as all-`False` output booleans.
- Object requirements are minimum-count thresholds from config.

### I/O and Reporting

- Never mutate input ROOT files.
- Write outputs deterministically.
- Preserve report schema unless intentionally versioning it.
- Keep `input_config` in reports for reproducibility.

## Test Expectations

When behavior changes, update/add tests for:

- config defaults and validation
- trigger/object filtering behavior
- offset + `n_events` range handling
- cutflow labels/counts
- missing trigger/object branch handling
- CLI and programmatic entrypoints

## Completion Checklist

1. Run syntax checks on changed Python files.
2. Run `ruff check .` (format if needed).
3. Run strict mypy on changed files.
4. Run `pytest -q` (or targeted subset while iterating).
5. Update `README.md` if behavior/CLI/config changes.
6. Summarize changed files and executed checks.
