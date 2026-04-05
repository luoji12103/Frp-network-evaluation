"""Simple sequential scheduler for probe execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScheduledStep:
    """A lazily executed orchestration step."""

    name: str
    runner: Callable[[], Awaitable[Any]]


async def run_steps(steps: Iterable[ScheduledStep]) -> list[Any]:
    """Run scheduled steps sequentially and collect their results."""
    results: list[Any] = []
    for step in steps:
        results.append(await step.runner())
    return results
