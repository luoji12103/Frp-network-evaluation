# Staging Panel Debug Stack

This repository now includes an isolated staging stack for the rewritten panel UI.

## Intended Server Layout

- debug worktree: `/root/server/Frp-network-evaluation-saas-debug`
- runtime root: `/root/server/mc-netprobe-panel-staging`
- compose file: [`docker-compose.staging.yml`](../docker-compose.staging.yml)
- startup helper: [`bin/start_staging_panel_debug.sh`](../bin/start_staging_panel_debug.sh)

The staging stack is intentionally isolated from production:

- compose project name: `frp-network-evaluation-staging`
- panel port: `18765`
- panel container: `mc-netprobe-panel-staging`
- bridge container: `mc-netprobe-panel-control-bridge-staging`
- runtime data lives only under `/root/server/mc-netprobe-panel-staging/{data,config/agent,results,logs,env}`

## What The Helper Does

`bin/start_staging_panel_debug.sh` performs the full staging bootstrap:

1. Creates the isolated runtime directories.
2. Writes or updates `env/staging.env` with admin credentials and build metadata.
3. Builds and starts the staging panel plus panel control bridge.
4. Seeds fixture data through `python -m controller.staging_seed`.
5. Starts the three simulated agents:
   - `client-sim`
   - `relay-sim`
   - `server-sim`
6. Waits until the simulated agents pair and start reporting healthy push connectivity.

## Common Server Commands

```bash
cd /root/server/Frp-network-evaluation-saas-debug
bash bin/start_staging_panel_debug.sh
docker compose -f docker-compose.staging.yml --env-file /root/server/mc-netprobe-panel-staging/env/staging.env ps
curl -s http://127.0.0.1:18765/api/v1/version | jq
curl -s http://127.0.0.1:18765/api/v1/public-dashboard | jq '.build'
```

Optional fixture toggle:

```bash
STAGING_INCLUDE_ACTIVE_BLOCKER=1 bash bin/start_staging_panel_debug.sh
```

That mode is useful for blocker CTA verification, but it will intentionally keep an active fixture run in the database and can interfere with manual-run E2E checks.
