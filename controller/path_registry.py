"""Canonical path registry shared by orchestrators, storage, and UI layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PathFamily = Literal["public", "diagnostic", "system", "legacy"]
PathVisibility = Literal["public", "admin"]


@dataclass(frozen=True, slots=True)
class PathSpec:
    path_id: str
    family: PathFamily
    visibility: PathVisibility
    source_role: str
    probe_kinds: tuple[str, ...]
    target_ref: str | None
    roles: tuple[str, ...]
    legacy_labels: tuple[str, ...] = ()


PATH_SPECS: dict[str, PathSpec] = {
    "client_to_relay_public": PathSpec(
        path_id="client_to_relay_public",
        family="public",
        visibility="public",
        source_role="client",
        probe_kinds=("ping", "tcp_probe"),
        target_ref="relay_public_probe",
        roles=("client", "relay"),
        legacy_labels=("client_to_relay",),
    ),
    "client_to_mc_public": PathSpec(
        path_id="client_to_mc_public",
        family="public",
        visibility="public",
        source_role="client",
        probe_kinds=("mc_tcp_probe",),
        target_ref="mc_public",
        roles=("client",),
    ),
    "client_to_iperf_public": PathSpec(
        path_id="client_to_iperf_public",
        family="public",
        visibility="public",
        source_role="client",
        probe_kinds=("throughput",),
        target_ref="iperf_public",
        roles=("client",),
    ),
    "relay_to_server_backend_mc": PathSpec(
        path_id="relay_to_server_backend_mc",
        family="diagnostic",
        visibility="admin",
        source_role="relay",
        probe_kinds=("ping", "tcp_probe"),
        target_ref="server_backend_mc",
        roles=("relay", "server"),
        legacy_labels=("relay_to_server", "server_to_local_mc"),
    ),
    "relay_to_server_backend_iperf": PathSpec(
        path_id="relay_to_server_backend_iperf",
        family="diagnostic",
        visibility="admin",
        source_role="relay",
        probe_kinds=("throughput",),
        target_ref="server_backend_iperf",
        roles=("relay", "server"),
        legacy_labels=("relay_to_server", "server_iperf_direct"),
    ),
    "server_to_relay_public": PathSpec(
        path_id="server_to_relay_public",
        family="diagnostic",
        visibility="admin",
        source_role="server",
        probe_kinds=("ping", "tcp_probe"),
        target_ref="relay_public_probe",
        roles=("server", "relay"),
    ),
    "client_system": PathSpec(
        path_id="client_system",
        family="system",
        visibility="admin",
        source_role="client",
        probe_kinds=("system_snapshot",),
        target_ref=None,
        roles=("client",),
    ),
    "relay_system": PathSpec(
        path_id="relay_system",
        family="system",
        visibility="admin",
        source_role="relay",
        probe_kinds=("system_snapshot",),
        target_ref=None,
        roles=("relay",),
    ),
    "server_system": PathSpec(
        path_id="server_system",
        family="system",
        visibility="admin",
        source_role="server",
        probe_kinds=("system_snapshot",),
        target_ref=None,
        roles=("server",),
    ),
}

LEGACY_ONLY_PATHS = (
    "client_to_relay",
    "relay_to_server",
    "server_to_local_mc",
    "server_iperf_direct",
    "server_iperf_public",
    "client_to_mc_public_load",
    "client_to_mc_public_load_idle",
    "client_to_mc_public_load_loaded",
    "client_to_iperf_public_load",
    "server_iperf_public_load",
)

DEFAULT_PATH_ORDER = (
    "client_to_relay_public",
    "client_to_mc_public",
    "client_to_iperf_public",
    "relay_to_server_backend_mc",
    "relay_to_server_backend_iperf",
    "server_to_relay_public",
    "client_system",
    "relay_system",
    "server_system",
    *LEGACY_ONLY_PATHS,
)

PUBLIC_PATH_IDS = tuple(path_id for path_id, spec in PATH_SPECS.items() if spec.visibility == "public")
PUBLIC_ROLE_IDS = ("client", "relay", "server")
PUBLIC_ROLE_PATHS = {
    "client": ("client_to_relay_public", "client_to_mc_public", "client_to_iperf_public"),
    "relay": ("client_to_relay_public",),
    "server": (),
}
PUBLIC_PATH_ROLES = {path_id: spec.roles for path_id, spec in PATH_SPECS.items() if spec.visibility == "public"}


def get_path_spec(path_id: str | None) -> PathSpec | None:
    if not path_id:
        return None
    return PATH_SPECS.get(str(path_id))


def canonical_path_id(path_label: str | None, probe_name: str | None = None, metric_name: str | None = None) -> str | None:
    if not path_label:
        return None
    label = str(path_label)
    if label in PATH_SPECS:
        return label
    if label == "client_to_relay":
        return "client_to_relay_public"
    if label == "relay_to_server":
        if (probe_name or "") == "throughput" or str(metric_name or "").startswith("throughput_"):
            return "relay_to_server_backend_iperf"
        return "relay_to_server_backend_mc"
    if label == "server_to_local_mc":
        return "relay_to_server_backend_mc"
    if label == "server_iperf_direct":
        return "relay_to_server_backend_iperf"
    return label


def expand_path_candidates(path_labels: list[str] | None) -> list[str] | None:
    if not path_labels:
        return None
    expanded: list[str] = []
    for label in path_labels:
        if label not in expanded:
            expanded.append(label)
        spec = get_path_spec(label)
        if spec:
            for legacy in spec.legacy_labels:
                if legacy not in expanded:
                    expanded.append(legacy)
    return expanded


def path_visibility(path_id: str | None) -> str:
    spec = get_path_spec(path_id)
    return spec.visibility if spec is not None else "admin"


def path_family(path_id: str | None) -> str:
    spec = get_path_spec(path_id)
    return spec.family if spec is not None else "legacy"
