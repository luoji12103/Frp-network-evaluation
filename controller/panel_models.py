"""Shared schemas for the panel and agent HTTP APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from controller.scenario import ScenariosConfig, ServiceConfig, ServicesConfig, ThresholdsConfig


SUPPORTED_AGENT_PROTOCOL_VERSION = "1"

NodeRole = Literal["client", "relay", "server"]
RuntimeMode = Literal["docker-linux", "native-macos", "native-windows"]
RunKind = Literal["system", "baseline", "capacity", "full"]
ChannelStateValue = Literal["unknown", "ok", "error"]
NodeSummaryStatus = Literal["online", "push-only", "pull-only", "offline", "unpaired", "disabled"]
ControlTargetKind = Literal["node", "panel"]
ControlActionName = Literal["status", "start", "stop", "restart", "tail_log", "sync_runtime", "pause_scheduler", "resume_scheduler"]
ControlActionStatus = Literal["queued", "running", "completed", "failed", "canceled"]


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
    configured_pull_url: str | None = None
    enabled: bool = True


class PairCodeResponse(BaseModel):
    """Pair code and operator instructions."""

    node_id: int
    node_name: str
    pair_code: str
    expires_at: str
    startup_command: str
    fallback_command: str | None = None


class AgentIdentity(BaseModel):
    """Stable identity reported by an agent."""

    node_name: str
    role: NodeRole
    runtime_mode: RuntimeMode
    protocol_version: str
    platform_name: str
    hostname: str
    agent_version: str = "1"

    @field_validator("protocol_version")
    @classmethod
    def validate_protocol_version(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("protocol_version is required")
        return normalized


class AgentEndpointReport(BaseModel):
    """Runtime endpoint details reported by an agent."""

    listen_host: str = "0.0.0.0"
    listen_port: int = 9870
    advertise_url: str | None = None
    control_listen_port: int | None = None
    control_url: str | None = None


class AgentCapabilities(BaseModel):
    """Transport capabilities supported by an agent."""

    pull_http: bool = True
    heartbeat_queue: bool = True
    result_lookup: bool = True


class AgentRuntimeStatus(BaseModel):
    """Mutable runtime state included in heartbeats and status checks."""

    paired: bool
    started_at: str
    last_heartbeat_at: str | None = None
    last_error: str | None = None
    environment: dict[str, Any] = Field(default_factory=dict)


class AgentPairRequest(BaseModel):
    """Initial pairing request sent by an agent to the panel."""

    pair_code: str
    identity: AgentIdentity
    endpoint: AgentEndpointReport
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)


class AgentPairResponse(BaseModel):
    """Pairing response returned by the panel."""

    ok: bool = True
    node_id: int
    topology_id: int
    node_token: str
    panel_url: str
    protocol_version: str = SUPPORTED_AGENT_PROTOCOL_VERSION
    identity: AgentIdentity
    endpoint: AgentEndpointReport
    capabilities: AgentCapabilities


class AgentTaskDispatch(BaseModel):
    """Task dispatched to an agent through pull or heartbeat queue."""

    job_id: int | None = None
    run_id: str | None = None
    task: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    lease_expires_at: str | None = None
    timeout_sec: float | None = None


class AgentTaskCompletion(BaseModel):
    """Task completion returned from an agent."""

    job_id: int | None = None
    run_id: str | None = None
    task: str | None = None
    result: dict[str, Any]


class AgentHeartbeatRequest(BaseModel):
    """Periodic heartbeat from an agent to the panel."""

    endpoint: AgentEndpointReport
    runtime_status: AgentRuntimeStatus
    completed_jobs: list[AgentTaskCompletion] = Field(default_factory=list)


class AgentHeartbeatResponse(BaseModel):
    """Heartbeat acknowledgement and leased jobs."""

    ok: bool = True
    jobs: list[AgentTaskDispatch] = Field(default_factory=list)
    status: str = "accepted"


class AgentStatusResponse(BaseModel):
    """Token-protected full agent status used by the panel."""

    identity: AgentIdentity
    endpoint: AgentEndpointReport
    capabilities: AgentCapabilities
    runtime_status: AgentRuntimeStatus


class AgentHealthResponse(BaseModel):
    """Minimal unauthenticated local healthcheck payload."""

    ok: bool = True
    status: str = "healthy"
    started_at: str


class RuntimeSummary(BaseModel):
    """Structured runtime summary for a managed process or service."""

    state: str = "unknown"
    checked_at: str | None = None
    last_error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SupervisorSummary(BaseModel):
    """Supervisor-facing state resolved by a host control bridge."""

    control_available: bool = False
    bridge_url: str | None = None
    supervisor_state: str = "unknown"
    process_state: str = "unknown"
    pid_or_container_id: str | None = None
    log_location: str | None = None
    last_error: str | None = None
    checked_at: str | None = None


class BridgeActionRequest(BaseModel):
    """Allowlisted action request sent to a control bridge."""

    action: ControlActionName
    tail_lines: int | None = Field(default=None, ge=1, le=200)


class BridgeActionResponse(BaseModel):
    """Normalized response returned by a control bridge."""

    ok: bool = True
    accepted: bool = False
    state: str = "unknown"
    human_summary: str
    raw_runtime: dict[str, Any] = Field(default_factory=dict)
    runtime: RuntimeSummary = Field(default_factory=RuntimeSummary)
    supervisor: SupervisorSummary = Field(default_factory=SupervisorSummary)
    log_location: str | None = None
    log_excerpt: list[str] = Field(default_factory=list)
    error: str | None = None


class AdminControlActionRequest(BaseModel):
    """Admin-triggered lifecycle or runtime action."""

    action: ControlActionName
    actor: str = "admin-ui"
    tail_lines: int | None = Field(default=None, ge=1, le=200)
    confirmation_token: str | None = None


class ControlActionEnvelope(BaseModel):
    """Persisted control action returned by admin APIs."""

    id: int
    target_kind: ControlTargetKind
    target_id: int | None = None
    action: ControlActionName
    status: ControlActionStatus
    confirmation_required: bool = False
    requested_by: str
    requested_at: str
    started_at: str | None = None
    finished_at: str | None = None
    transport: str | None = None
    result_summary: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    target_name: str | None = None
    is_dangerous: bool = False
    has_log_excerpt: bool = False
    has_runtime_snapshot: bool = False
    active: bool = False
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    log_excerpt: list[str] = Field(default_factory=list)
    log_location: str | None = None
    runtime_snapshot: dict[str, Any] = Field(default_factory=dict)
    failure: dict[str, Any] = Field(default_factory=dict)
    audit_payload: dict[str, Any] = Field(default_factory=dict)


class AdminControlActionCreateResponse(BaseModel):
    """Response returned when an admin submits a control action."""

    ok: bool = True
    queued: bool = False
    confirmation_required: bool = False
    confirmation_token: str | None = None
    action: ControlActionEnvelope | None = None


class RunEventEnvelope(BaseModel):
    """Lightweight event emitted during a monitoring run."""

    id: int
    run_id: str
    event_kind: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    severity: str = "info"
    code: str | None = None
    created_at: str


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
    summary: dict[str, Any]
    nodes: list[dict[str, Any]]
    latest_runs: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    paths: list[dict[str, Any]] = Field(default_factory=list)
    history: dict[str, Any]


class HistoryResponse(BaseModel):
    """Metric history query response."""

    samples: list[dict[str, Any]]


class AlertAcknowledgeRequest(BaseModel):
    """Acknowledge one or more alerts."""

    actor: str = "admin"


class AlertSilenceRequest(BaseModel):
    """Silence a fingerprinted alert until a fixed time."""

    silenced_until: str
    reason: str = ""
    actor: str = "admin"


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
