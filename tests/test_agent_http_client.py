from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from controller.agent_http_client import AgentHttpClient, AgentHttpError
from controller.panel_models import AgentCapabilities, AgentEndpointReport, AgentIdentity, NodeUpsertRequest
from controller.panel_store import PanelStore


def build_paired_node(tmp_path: Path) -> tuple[PanelStore, dict[str, object]]:
    store = PanelStore(db_path=tmp_path / "monitor.db", secret_path=tmp_path / "panel-secret.txt")
    node = store.upsert_node(
        NodeUpsertRequest(
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            configured_pull_url="http://relay.example:9870",
            enabled=True,
        )
    )
    pair_code, _ = store.create_pair_code(int(node["id"]))
    store.pair_agent(
        identity=AgentIdentity(
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            protocol_version="1",
            platform_name="linux",
            hostname="relay-1-host",
            agent_version="test-agent",
        ),
        pair_code=pair_code,
        endpoint=AgentEndpointReport(
            listen_host="0.0.0.0",
            listen_port=9870,
            advertise_url="http://relay.example:9870",
        ),
        capabilities=AgentCapabilities(),
    )
    paired = store.get_node(int(node["id"]))
    assert paired is not None
    return store, paired


def test_missing_pull_contract_route_is_classified_as_protocol_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store, node = build_paired_node(tmp_path)
    client = AgentHttpClient(store=store)

    response = httpx.Response(
        404,
        request=httpx.Request("POST", "http://relay.example:9870/api/v1/jobs/run"),
        json={"detail": "Not Found"},
    )

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def request(self, method: str, url: str, headers=None, json=None) -> httpx.Response:
            return response

    monkeypatch.setattr(httpx, "Client", FakeClient)

    with pytest.raises(AgentHttpError) as excinfo:
        client.run_job(node=node, job_id=None, run_id="run-1", task="ping", payload={"host": "relay.example", "timeout_sec": 1.0})

    assert excinfo.value.code == "protocol_mismatch"
    assert "did not expose /api/v1/jobs/run" in excinfo.value.message
