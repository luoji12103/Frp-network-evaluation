"""Relay role agent."""

from __future__ import annotations

import asyncio

from agents import run_agent


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_agent("relay")))
