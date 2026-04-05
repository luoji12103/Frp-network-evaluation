"""Path descriptors used by the orchestrator and exporters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PathSpec:
    """A logical measurement path in the topology."""

    label: str
    source_node: str
    target_host: str
    port: int | None = None
    category: str = "network"

    @property
    def endpoint(self) -> str:
        if self.port is None:
            return self.target_host
        return f"{self.target_host}:{self.port}"
