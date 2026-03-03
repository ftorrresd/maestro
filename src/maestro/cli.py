from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, cast

import typer

from .config import load_config_source
from .skimmer import run_from_config

app = typer.Typer(
    help="Maestro CLI for CMS NanoAOD workflows.",
    no_args_is_help=True,
)


@app.callback()
def app_callback() -> None:
    """Maestro command group."""


def _print_run_summary(report: dict[str, Any], *, output_path: Path) -> None:
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


@app.command("skim")
def skim_command(
    config_source: str = typer.Argument(
        ...,
        help="Config file path or inline JSON string",
    ),
) -> None:
    """Run event skimming from a config source."""
    config = load_config_source(config_source)
    output_path = Path(config.output)
    report = run_from_config(config)
    _print_run_summary(report, output_path=output_path)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = list(argv) if argv is not None else None
    app(args=args, prog_name="maestro", standalone_mode=False)
