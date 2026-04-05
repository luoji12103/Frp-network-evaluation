from pathlib import Path

from exporters.csv_exporter import export_csv
from exporters.html_report import export_html
from exporters.json_exporter import export_json
from probes.common import ProbeResult, RunResult, ThresholdFinding


def test_exporters_smoke(tmp_path: Path) -> None:
    run_result = RunResult(
        run_id="run-20260403-000000",
        project="mc-frp-netprobe",
        started_at="2026-04-03T00:00:00+00:00",
        finished_at="2026-04-03T00:01:00+00:00",
        environment={"platform": "test"},
        probes=[
            ProbeResult(
                name="ping",
                source="client",
                target="127.0.0.1",
                success=True,
                metrics={"rtt_avg_ms": 1.0},
                metadata={"path_label": "client_to_relay"},
            )
        ],
        threshold_findings=[
            ThresholdFinding(
                path_label="client_to_relay",
                probe_name="ping",
                metric="rtt_avg_ms",
                threshold=0.5,
                actual=1.0,
                message="rtt_avg_ms exceeded the configured maximum",
            )
        ],
        conclusion=["test conclusion"],
    )

    raw_path = export_json(run_result, tmp_path)
    csv_path = export_csv(run_result, tmp_path)
    html_path = export_html(run_result, tmp_path)

    assert raw_path.exists()
    assert csv_path.exists()
    assert html_path.exists()
    assert "test conclusion" in html_path.read_text(encoding="utf-8")
