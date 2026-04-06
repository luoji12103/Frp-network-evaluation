"""Shared schemas for the panel and agent HTTP APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from controller.scenario import ScenariosConfig, ServiceConfig, ServicesConfig, ThresholdsConfig


NodeRole = Literal["client", "relay", "server"]
RuntimeMode = Literal["docker-linux", "native-macos", "native-windows"]
RunKind = Literal["system", "baseline", "capacity", "full"]


class PanelSettings(BaseModel):
    """Persistent topology-wide configuration managed by the panel."""

    topology_name: str = "mc-netprobe-monitor"
    services: ServicesConfig = Field(default_factory=lambda: build_default_services())
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    scenarios: ScenariosConfig = Field(default_factory=ScenariosConfig)


class NodeUpsertRequest(BaseModel):
    """Create or update a monitored node."""

    id: int | None = None
    node_name: str
    role: NodeRole
    runtime_mode: RuntimeMode
    agent_url: str | None = None
    enabled: bool = True


class PairCodeResponse(BaseModel):
    """Pair code and operator instructions."""

    node_id: int
    node_name: str
    pair_code: str
    expires_at: str
    startup_command: str
    fallback_command: str | None = None


class AgentPairRequest(BaseModel):
    """Initial pairing request sent by an agent to the panel."""

    node_name: str
    role: NodeRole
    runtime_mode: RuntimeMode
    pair_code: str
    agent_url: str | None = None
    advertise_url: str | None = None
    listen_host: str = "0.0.0.0"
    listen_port: int = 9870
    platform_name: str
    hostname: str
    version: str = "1"


class AgentPairResponse(BaseModel):
    """Pairing response returned by the panel."""

    ok: bool = True
    node_id: int
    topology_id: int
    node_token: str
    panel_url: str
    node_name: str
    role: NodeRole
    listen_host: str
    listen_port: int
    advertise_url: str | None = None


class AgentCompletedJob(BaseModel):
    """A job result returned from an agent heartbeat."""

    job_id: int
    result: dict[str, Any]


class AgentHeartbeatRequest(BaseModel):
    """Periodic heartbeat from an agent to the panel."""

    node_name: str
    agent_url: str | None = None
    advertise_url: str | None = None
    status: dict[str, Any] = Field(default_factory=dict)
    completed_jobs: list[AgentCompletedJob] = Field(default_factory=list)


class PanelJobDispatch(BaseModel):
    """Queued job handed to an agent via heartbeat."""

    job_id: int
    task: str
    payload: dict[str, Any]
    created_at: str


class AgentHeartbeatResponse(BaseModel):
    """Heartbeat acknowledgement and pending jobs."""

    ok: bool = True
    jobs: list[PanelJobDispatch] = Field(default_factory=list)
    status: str = "accepted"


class AgentJobRequest(BaseModel):
    """Direct pull-mode job sent from the panel to an agent."""

    job_id: int | None = None
    run_id: str | None = None
    task: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentJobResponse(BaseModel):
    """Immediate result from an agent-run task."""

    ok: bool = True
    job_id: int | None = None
    run_id: str
    result: dict[str, Any]


class DashboardSnapshot(BaseModel):
    """Top-level dashboard response rendered by the panel."""

    topology_id: int
    settings: dict[str, Any]
    schedules: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    latest_runs: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    history: dict[str, Any]


class PublicDashboardSnapshot(BaseModel):
    """Public-safe dashboard response for the unauthenticated view."""

    topology_id: int
    topology_name: str
    summary: dict[str, int]
    nodes: list[dict[str, Any]]
    latest_runs: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    history: dict[str, Any]


class HistoryResponse(BaseModel):
    """Metric history query response."""

    samples: list[dict[str, Any]]


class ManualRunRequest(BaseModel):
    """Manual run trigger from the UI or API."""

    run_kind: RunKind = "full"
    source: str = "manual"


def build_default_services() -> ServicesConfig:
    """Build the single-topology default service endpoints."""
    return ServicesConfig(
        relay_probe=ServiceConfig(host="", port=22),
        mc_public=ServiceConfig(host="", port=25565),
        iperf_public=ServiceConfig(host="", port=5201),
        mc_local=ServiceConfig(host="127.0.0.1", port=25565),
        iperf_local=ServiceConfig(host="0.0.0.0", port=5201),
    )
