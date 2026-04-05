import json

from probes.throughput import parse_iperf3_output


def test_parse_iperf3_output() -> None:
    payload = {
        "end": {
            "sum_sent": {"bits_per_second": 12_000_000, "retransmits": 1, "seconds": 10},
            "sum_received": {"bits_per_second": 11_500_000, "seconds": 10},
        },
        "intervals": [
            {"sum": {"bits_per_second": 11_000_000}},
            {"sum": {"bits_per_second": 12_000_000}},
            {"sum": {"bits_per_second": 13_000_000}},
        ],
    }
    metrics, samples = parse_iperf3_output(json.dumps(payload), reverse=False)
    assert metrics["throughput_up_mbps"] == 12.0
    assert metrics["retransmits"] == 1
    assert len(samples) == 3
