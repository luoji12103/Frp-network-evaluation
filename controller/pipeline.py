"""Shared run pipeline used by CLI and Web UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from controller.orchestrator import Orchestrator
from controller.scenario import ScenariosConfig, ThresholdsConfig, TopologyConfig, load_scenarios, load_thresholds, load_topology
from exporters.csv_exporter import export_csv
from exporters.html_report import export_html
from exporters.json_exporter import export_json
from probes.common import RunResult


@dataclass(slots=True)
class RunArtifacts:
    """Materialized files and payloads for a completed run."""

    run_id: str
    output_dir: Path
    raw_path: Path
    csv_path: Path
    html_path: Path
    run_result: RunResult


async def execute_run(
    topology: TopologyConfig,
    thresholds: ThresholdsConfig,
    scenarios: ScenariosConfig,
    output_root: str | Path = "results",
    run_id: str | None = None,
) -> RunArtifacts:
    """Run the orchestrator and export all artifacts."""
    resolved_run_id = run_id or datetime.now().astimezone().strftime("run-%Y%m%d-%H%M%S")
    output_dir = Path(output_root) / resolved_run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    orchestrator = Orchestrator(
        topology=topology,
        thresholds=thresholds,
        scenarios=scenarios,
        run_id=resolved_run_id,
    )
    run_result = await orchestrator.run()
    raw_path = export_json(run_result, output_dir)
    csv_path = export_csv(run_result, output_dir)
    html_path = export_html(run_result, output_dir)
    return RunArtifacts(
        run_id=resolved_run_id,
        output_dir=output_dir,
        raw_path=raw_path,
        csv_path=csv_path,
        html_path=html_path,
        run_result=run_result,
    )


async def execute_run_from_paths(
    topology_path: str | Path,
    thresholds_path: str | Path,
    scenarios_path: str | Path,
    output_root: str | Path = "results",
    run_id: str | None = None,
) -> RunArtifacts:
    """Load YAML configs and run the orchestrator."""
    topology = load_topology(topology_path)
    thresholds = load_thresholds(thresholds_path)
    scenarios = load_scenarios(scenarios_path)
    return await execute_run(
        topology=topology,
        thresholds=thresholds,
        scenarios=scenarios,
        output_root=output_root,
        run_id=run_id,
    )
