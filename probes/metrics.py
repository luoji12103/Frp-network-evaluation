"""Statistical helpers for probe aggregation."""

from __future__ import annotations

import math
import statistics
from typing import Iterable


def percentile(values: Iterable[float], value: float) -> float | None:
    """Compute an interpolated percentile."""
    ordered = sorted(float(item) for item in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * (value / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def jitter(values: Iterable[float]) -> float | None:
    """Return the mean absolute delta between adjacent samples."""
    series = [float(item) for item in values]
    if len(series) < 2:
        return 0.0 if series else None
    deltas = [abs(series[index] - series[index - 1]) for index in range(1, len(series))]
    return sum(deltas) / len(deltas)


def summarize_latency(values: Iterable[float]) -> dict[str, float | None]:
    """Return a common latency summary dictionary."""
    series = [float(item) for item in values]
    if not series:
        return {
            "min_ms": None,
            "avg_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "max_ms": None,
            "jitter_ms": None,
        }
    return {
        "min_ms": min(series),
        "avg_ms": sum(series) / len(series),
        "p95_ms": percentile(series, 95),
        "p99_ms": percentile(series, 99),
        "max_ms": max(series),
        "jitter_ms": jitter(series),
    }


def success_rate(successes: int, attempts: int) -> float | None:
    """Return percentage success rate."""
    if attempts <= 0:
        return None
    return (successes / attempts) * 100.0


def stability_score(values: Iterable[float]) -> float | None:
    """Return a simple 0-100 stability score based on coefficient of variation."""
    series = [float(item) for item in values if item is not None]
    if not series:
        return None
    mean_value = sum(series) / len(series)
    if mean_value <= 0:
        return None
    if len(series) == 1:
        return 100.0
    coefficient = statistics.pstdev(series) / mean_value
    return max(0.0, min(100.0, 100.0 - (coefficient * 100.0)))


def calculate_load_inflation(idle_connect_avg_ms: float | None, loaded_connect_avg_ms: float | None) -> float | None:
    """Return additional delay under load."""
    if idle_connect_avg_ms is None or loaded_connect_avg_ms is None:
        return None
    return loaded_connect_avg_ms - idle_connect_avg_ms
