from controller.orchestrator import evaluate_probe_thresholds
from controller.scenario import ThresholdsConfig
from probes.common import ProbeResult


def test_threshold_evaluation_flags_ping_violation() -> None:
    probe = ProbeResult(
        name="ping",
        source="client",
        target="relay",
        success=True,
        metrics={"rtt_avg_ms": 200.0, "packet_loss_pct": 0.0, "rtt_p95_ms": 210.0, "jitter_ms": 10.0},
        metadata={"path_label": "client_to_relay_public"},
    )
    findings = evaluate_probe_thresholds(probe, ThresholdsConfig())
    assert any(finding.metric == "rtt_avg_ms" for finding in findings)
