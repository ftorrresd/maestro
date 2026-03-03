#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge skim report JSON files")
    parser.add_argument("--reports", nargs="+", required=True, help="Report JSON paths")
    parser.add_argument("--output", required=True, help="Merged report output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reports: list[dict[str, Any]] = []
    for path_str in args.reports:
        path = Path(path_str)
        with path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
        if not isinstance(report, dict):
            raise ValueError(f"Report is not a JSON object: {path}")
        reports.append(report)

    total_scanned = 0
    total_selected = 0
    for report in reports:
        processed = report.get("processed_event_range", {})
        if isinstance(processed, dict):
            total_scanned += int(processed.get("n_scanned", 0))
            total_selected += int(processed.get("n_selected", 0))

    merged = {
        "n_reports": len(reports),
        "total_n_scanned": total_scanned,
        "total_n_selected": total_selected,
        "selection_efficiency": (float(total_selected) / total_scanned)
        if total_scanned
        else 0.0,
        "reports": reports,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)


if __name__ == "__main__":
    main()
