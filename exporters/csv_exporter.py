"""CSV exporter."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from probes.common import RunResult


def export_csv(run_result: RunResult, output_dir: str | Path) -> Path:
    """Write summary.csv for a run result."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "summary.csv"

    rows = [_probe_to_row(probe) for probe in run_result.probes]
    fieldnames = sorted({key for row in rows for key in row.keys()})

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return target


def _probe_to_row(probe: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path_label": probe.metadata.get("path_label"),
        "probe_name": probe.name,
        "source": probe.source,
        "target": probe.target,
        "success": probe.success,
        "error": probe.error,
    }
    for key, value in probe.metrics.items():
        row[key] = value
    return row
