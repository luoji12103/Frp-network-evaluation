"""Configuration models and YAML loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError


NodeOS = Literal["windows", "macos", "linux"]
NodeRole = Literal["client", "relay", "server"]


class NodeConfig(BaseModel):
    role: NodeRole
    host: str
    os: NodeOS
    local: bool = False
    ssh_user: str | None = None
    ssh_port: int = 22
    project_root: str = "."
    python_bin: str = "python"


class ServiceConfig(BaseModel):
    host: str
    port: int


class NodesConfig(BaseModel):
    client: NodeConfig
    relay: NodeConfig
    server: NodeConfig


class ServicesConfig(BaseModel):
    relay_probe: ServiceConfig | None = None
    mc_public: ServiceConfig
    iperf_public: ServiceConfig
    mc_local: ServiceConfig
    iperf_local: ServiceConfig


class TopologyConfig(BaseModel):
    project_name: str = "mc-frp-netprobe"
    nodes: NodesConfig
    services: ServicesConfig


class PingThresholds(BaseModel):
    packet_loss_pct_max: float = 2.0
    rtt_avg_ms_max: float = 120.0
    rtt_p95_ms_max: float = 180.0
    jitter_ms_max: float = 20.0


class TcpThresholds(BaseModel):
    connect_avg_ms_max: float = 150.0
    connect_p95_ms_max: float = 250.0
    timeout_or_error_pct_max: float = 10.0


class ThroughputThresholds(BaseModel):
    throughput_up_mbps_min: float = 5.0
    throughput_down_mbps_min: float = 5.0


class LoadInflationThresholds(BaseModel):
    load_rtt_inflation_ms_max: float = 80.0
    loaded_timeout_pct_max: float = 15.0


class SystemThresholds(BaseModel):
    cpu_usage_pct_max: float = 90.0
    memory_usage_pct_max: float = 90.0


class ThresholdsConfig(BaseModel):
    ping: PingThresholds = Field(default_factory=PingThresholds)
    tcp: TcpThresholds = Field(default_factory=TcpThresholds)
    throughput: ThroughputThresholds = Field(default_factory=ThroughputThresholds)
    load_inflation: LoadInflationThresholds = Field(default_factory=LoadInflationThresholds)
    system: SystemThresholds = Field(default_factory=SystemThresholds)


class PingScenarioConfig(BaseModel):
    enabled: bool = True
    count: int = 4
    timeout_sec: float = 10.0


class TcpScenarioConfig(BaseModel):
    enabled: bool = True
    attempts: int = 6
    interval_ms: int = 250
    timeout_ms: int = 3000
    concurrency: int = 1


class ThroughputScenarioConfig(BaseModel):
    enabled: bool = True
    duration_sec: int = 10
    parallel_streams: int = 1
    timeout_sec: float = 20.0


class SystemScenarioConfig(BaseModel):
    enabled: bool = True
    sample_interval_sec: float = 1.0
    process_names: list[str] = Field(default_factory=lambda: ["frps", "frpc", "java", "java.exe"])


class LoadInflationScenarioConfig(BaseModel):
    enabled: bool = True
    baseline_attempts: int = 8
    probe_interval_ms: int = 500
    timeout_ms: int = 3000
    duration_sec: int = 10


class ScenariosConfig(BaseModel):
    ping: PingScenarioConfig = Field(default_factory=PingScenarioConfig)
    tcp: TcpScenarioConfig = Field(default_factory=TcpScenarioConfig)
    throughput: ThroughputScenarioConfig = Field(default_factory=ThroughputScenarioConfig)
    system: SystemScenarioConfig = Field(default_factory=SystemScenarioConfig)
    load_inflation: LoadInflationScenarioConfig = Field(default_factory=LoadInflationScenarioConfig)


def load_topology(path: str | Path) -> TopologyConfig:
    return _load_model(path, TopologyConfig)


def load_thresholds(path: str | Path) -> ThresholdsConfig:
    return _load_model(path, ThresholdsConfig)


def load_scenarios(path: str | Path) -> ScenariosConfig:
    return _load_model(path, ScenariosConfig)


def _load_model(path: str | Path, model_cls: type[BaseModel]) -> BaseModel:
    file_path = Path(path)
    raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid configuration file: {file_path}") from exc
