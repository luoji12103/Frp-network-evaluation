from probes.ping import parse_ping_output


WINDOWS_OUTPUT = """
Pinging 127.0.0.1 with 32 bytes of data:
Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
Reply from 127.0.0.1: bytes=32 time<1ms TTL=128
Reply from 127.0.0.1: bytes=32 time=1ms TTL=128
Reply from 127.0.0.1: bytes=32 time=1ms TTL=128

Ping statistics for 127.0.0.1:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 0ms, Maximum = 1ms, Average = 0ms
"""

LINUX_OUTPUT = """
PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.034 ms
64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.045 ms
64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.038 ms
64 bytes from 127.0.0.1: icmp_seq=4 ttl=64 time=0.042 ms

--- 127.0.0.1 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3072ms
rtt min/avg/max/mdev = 0.034/0.039/0.045/0.004 ms
"""

MACOS_OUTPUT = """
PING localhost (127.0.0.1): 56 data bytes
64 bytes from 127.0.0.1: icmp_seq=0 ttl=64 time=0.043 ms
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.052 ms
64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.046 ms
64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.050 ms

--- localhost ping statistics ---
4 packets transmitted, 4 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 0.043/0.048/0.052/0.003 ms
"""


def test_parse_windows_ping_output() -> None:
    parsed = parse_ping_output(WINDOWS_OUTPUT)
    assert parsed["received"] == 4
    assert parsed["packet_loss_pct"] == 0.0
    assert parsed["rtt_max_ms"] == 1.0


def test_parse_linux_ping_output() -> None:
    parsed = parse_ping_output(LINUX_OUTPUT)
    assert parsed["sent"] == 4
    assert parsed["rtt_avg_ms"] == 0.039
    assert parsed["rtt_p95_ms"] is not None


def test_parse_macos_ping_output() -> None:
    parsed = parse_ping_output(MACOS_OUTPUT)
    assert parsed["received"] == 4
    assert parsed["rtt_min_ms"] == 0.043
    assert parsed["jitter_ms"] is not None
