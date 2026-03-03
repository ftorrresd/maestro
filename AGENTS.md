# AGENTS.md
Guide for agentic coding tools in this repository.

## Project Snapshot
- Language: Python
- Domain: CMS NanoAOD skimming with `uproot` + `awkward`
- Entrypoint: `skim.py`
- Tests: `tests/test_skim.py`
- Example config: `config_example.json`
- Docs: `README.md`
- Type config: `mypy.ini`

## Cursor/Copilot Rules
Checked paths requested by user:
- `.cursor/rules/`: not present
- `.cursorrules`: not present
- `.github/copilot-instructions.md`: not present
No extra Cursor/Copilot rules are active.

## Environment Setup
Preferred:
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
No package build step exists; use these checks as quality gate.

### Syntax
```bash
.venv/bin/python -m py_compile skim.py tests/test_skim.py
```

### Lint
```bash
.venv/bin/ruff check .
```

### Format
```bash
.venv/bin/ruff format .
```

### Type checking (strict)
```bash
.venv/bin/mypy --strict skim.py tests/test_skim.py
```

### Run all tests
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
CLI takes one positional argument: `config_source`.

### File config
```bash
.venv/bin/python skim.py config_example.json
```

### Inline JSON config
```bash
.venv/bin/python skim.py '{"input":"/path/to/in.root","output":"skim.root","triggers":[],"object_requirements":{},"keep_branches":[]}'
```

### Programmatic usage
```python
from skim import run_from_config

report = run_from_config(
    {
        "input": "/path/to/in.root",
        "output": "skim.root",
        "triggers": [],
        "object_requirements": {},
        "keep_branches": [],
    }
)
```

Expected outputs:
- ROOT output with skimmed `Events`
- `cutflow` histogram in output ROOT
- report JSON at `<output>.report.json`

## Code Style Guidelines
Follow existing patterns in `skim.py` and `tests/test_skim.py`.

### Imports
- Group imports: stdlib, third-party, local
- Keep imports explicit; no wildcard imports
- Keep ordering stable and readable

### Formatting
- Follow PEP 8 and Black-compatible style
- Prefer readability over dense one-liners
- Use trailing commas in multiline literals/calls

### Types
- Add annotations to new/changed functions
- Keep `mypy --strict` passing
- Prefer concrete generics (`list[str]`, `dict[str, int]`, etc.)
- Use structured schemas where useful (`pydantic.BaseModel`, `TypedDict`)
- Keep `Any` localized and justified

### Naming
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Tests: `test_<behavior>`

### Error Handling
- Validate user/config input early
- Raise specific exceptions (`ValueError`, `KeyError`, `FileNotFoundError`, `RuntimeError`)
- Include path/key/value context in error messages
- Do not silently swallow exceptions

### Analysis Logic
- Keep selection logic explicit and auditable
- Preserve cumulative cutflow semantics per stage
- Trigger logic is OR over requested triggers
- Missing trigger branches are treated as always `False`
- Missing configured triggers are written as all-`False` output booleans
- Object requirements are minimum-count thresholds from config

### I/O and Reporting
- Never modify input ROOT files
- Write outputs deterministically
- Preserve report schema unless intentionally versioning
- Keep `input_config` in report for reproducibility

### Comments and Docstrings
- Add docstrings for public/non-trivial functions
- Add comments only for non-obvious intent
- Avoid comments that just restate obvious code

## Test Expectations
When behavior changes, update/add tests for:
- config defaults and validation failures
- trigger/object filtering behavior
- offset and `n_events` slicing
- cutflow labels/counts
- missing trigger/object branch handling
- CLI and programmatic entrypoints

## Completion Checklist
1. Run `py_compile` on changed Python files
2. Run `ruff check .` (and format if needed)
3. Run strict mypy on changed files
4. Run `pytest -q` (or targeted tests during iteration)
5. Update `README.md` for CLI/config/output changes
6. Summarize changed files and executed commands
