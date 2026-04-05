"""CLI entrypoint for mc-netprobe."""

from __future__ import annotations

import argparse
import asyncio

from controller.pipeline import execute_run_from_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="mc-netprobe orchestrator")
    parser.add_argument("--topology", required=True)
    parser.add_argument("--thresholds", required=True)
    parser.add_argument("--scenarios", required=True)
    return parser


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    artifacts = await execute_run_from_paths(
        topology_path=args.topology,
        thresholds_path=args.thresholds,
        scenarios_path=args.scenarios,
    )
    print(f"Run complete: {artifacts.run_id}")
    print(f"raw.json: {artifacts.raw_path}")
    print(f"summary.csv: {artifacts.csv_path}")
    print(f"report.html: {artifacts.html_path}")
    if artifacts.run_result.threshold_findings:
        print(f"Threshold findings: {len(artifacts.run_result.threshold_findings)}")
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
