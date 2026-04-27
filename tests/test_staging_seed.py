from __future__ import annotations

from pathlib import Path

from controller.panel_store import PanelStore
from controller.staging_seed import seed_staging_snapshot


def test_staging_seed_writes_sim_env_and_fixture_shapes(tmp_path: Path) -> None:
    db_path = tmp_path / "monitor.db"
    env_path = tmp_path / "staging.env"

    payload = seed_staging_snapshot(db_path=db_path, env_path=env_path, include_active_blocker=True)
    store = PanelStore(db_path=db_path)

    assert len(payload["sim_nodes"]) == 3
    assert payload["fixtures"]["runs"]["completed_run_id"]
    assert payload["fixtures"]["runs"]["active_run_id"]

    env_text = env_path.read_text(encoding="utf-8")
    assert "CLIENT_SIM_PAIR_CODE=" in env_text
    assert "RELAY_SIM_PAIR_CODE=" in env_text
    assert "SERVER_SIM_PAIR_CODE=" in env_text
    assert "STAGING_SEED_SUMMARY_JSON=" in env_text

    nodes = store.list_nodes()
    assert any(node["node_name"] == "client-sim" for node in nodes)
    assert any(node["node_name"] == "relay-legacy-fixture" for node in nodes)
    assert any(node["node_name"] == "server-disabled-fixture" and node["status"] == "disabled" for node in nodes)

    alerts = store.query_alert_events(time_range_hours=24 * 365, limit=50)
    assert alerts["summary"]["acknowledged"] >= 2
    assert alerts["summary"]["silenced"] >= 1

    actions = store.list_control_actions(limit=20)
    assert len(actions) >= 3
    assert any(action["active"] for action in actions)

    runs = store.query_runs(time_range_hours=24 * 365, limit=20)
    assert len(runs) >= 2
