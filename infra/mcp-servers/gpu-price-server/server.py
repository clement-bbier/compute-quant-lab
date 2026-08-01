"""`gpu-price` MCP server — exposes GPU price snapshots (real) via FastMCP/stdio.

Wiring only: each tool delegates to a pure function in ``service``. The lake root is
resolved via ``$CLAUDE_PROJECT_DIR`` (Claude Code) or by walking up from this file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import service
from core.storage import ParquetPriceStore


def _snapshot_root() -> Path:
    """Parquet lake root: ``$CLAUDE_PROJECT_DIR/data/snapshots`` or a relative resolution."""
    base = os.environ.get("CLAUDE_PROJECT_DIR")
    root = Path(base) if base else Path(__file__).resolve().parents[3]
    return root / "data" / "snapshots"


_STORE = ParquetPriceStore(_snapshot_root())
mcp = FastMCP("gpu-price")


@mcp.tool()
def list_gpu_models(as_of: str | None = None) -> list[str]:
    """Known GPU models (real), sorted, bounded to the point-in-time ``as_of`` (ISO 8601 UTC)."""
    return service.list_gpu_models(_STORE, as_of=as_of)


@mcp.tool()
def latest_price(
    gpu_model: str, lease_type: str = "on_demand", as_of: str | None = None
) -> dict[str, Any]:
    """Latest observed price per source for ``gpu_model`` (real) + min/median/max summary."""
    return service.latest_price(_STORE, gpu_model, lease_type=lease_type, as_of=as_of)


@mcp.tool()
def price_history(
    gpu_model: str,
    start: str | None = None,
    as_of: str | None = None,
    source: str | None = None,
    lease_type: str | None = None,
) -> dict[str, Any]:
    """Time series of readings (real) for ``gpu_model`` within ``[start, as_of]``."""
    return service.price_history(
        _STORE, gpu_model, start=start, as_of=as_of, source=source, lease_type=lease_type
    )


@mcp.tool()
def summary_stats(
    gpu_model: str, lease_type: str | None = None, as_of: str | None = None
) -> dict[str, Any]:
    """Descriptive stats (real) for ``gpu_model`` prices, bounded to the point-in-time."""
    return service.summary_stats(_STORE, gpu_model, lease_type=lease_type, as_of=as_of)


@mcp.tool()
def query(sql: str) -> dict[str, Any]:
    """**Raw** DuckDB SQL against the ``prices`` view (the lake). No point-in-time guard."""
    return service.run_query(_STORE, sql)


if __name__ == "__main__":
    mcp.run()
