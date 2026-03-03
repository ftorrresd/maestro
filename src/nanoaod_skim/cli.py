from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Optional, Sequence, cast

from .config import load_config_source
from .skimmer import run_from_config


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
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


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    config = load_config_source(args.config_source)
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
