"""Smoke test : le serveur enregistre bien les 5 outils MCP."""

from __future__ import annotations

import asyncio


def test_server_registers_five_tools():
    import server

    tools = asyncio.run(server.mcp.list_tools())
    names = sorted(t.name for t in tools)
    assert names == ["latest_price", "list_gpu_models", "price_history", "query", "summary_stats"]
