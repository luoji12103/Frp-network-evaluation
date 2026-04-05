"""JSON exporter."""

from __future__ import annotations

import json
from pathlib import Path

from probes.common import RunResult


def export_json(run_result: RunResult, output_dir: str | Path) -> Path:
    """Write raw.json for a run result."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "raw.json"
    target.write_text(json.dumps(run_result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target
