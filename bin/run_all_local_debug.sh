#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
"$PYTHON_BIN" main.py \
  --topology config/topology.example.yaml \
  --thresholds config/thresholds.example.yaml \
  --scenarios config/scenarios.example.yaml
