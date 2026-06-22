"""Serveur MCP `gpu-price` — expose les snapshots de prix GPU (réel) via FastMCP/stdio.

Câblage seulement : chaque outil délègue à une fonction pure de ``service``. La racine du lac
est résolue via ``$CLAUDE_PROJECT_DIR`` (Claude Code) ou en remontant depuis ce fichier.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import service
from core.storage import ParquetPriceStore


def _snapshot_root() -> Path:
    """Racine du lac Parquet : ``$CLAUDE_PROJECT_DIR/data/snapshots`` ou résolution relative."""
    base = os.environ.get("CLAUDE_PROJECT_DIR")
    root = Path(base) if base else Path(__file__).resolve().parents[3]
    return root / "data" / "snapshots"


_STORE = ParquetPriceStore(_snapshot_root())
mcp = FastMCP("gpu-price")


@mcp.tool()
def list_gpu_models(as_of: str | None = None) -> list[str]:
    """Modèles GPU connus (réel), triés, bornés au point-in-time ``as_of`` (ISO 8601 UTC)."""
    return service.list_gpu_models(_STORE, as_of=as_of)


@mcp.tool()
def latest_price(
    gpu_model: str, lease_type: str = "on_demand", as_of: str | None = None
) -> dict[str, Any]:
    """Dernier prix observé par source pour ``gpu_model`` (réel) + résumé min/médian/max."""
    return service.latest_price(_STORE, gpu_model, lease_type=lease_type, as_of=as_of)


@mcp.tool()
def price_history(
    gpu_model: str,
    start: str | None = None,
    as_of: str | None = None,
    source: str | None = None,
    lease_type: str | None = None,
) -> dict[str, Any]:
    """Série temporelle des relevés (réel) de ``gpu_model`` dans ``[start, as_of]``."""
    return service.price_history(
        _STORE, gpu_model, start=start, as_of=as_of, source=source, lease_type=lease_type
    )


@mcp.tool()
def summary_stats(
    gpu_model: str, lease_type: str | None = None, as_of: str | None = None
) -> dict[str, Any]:
    """Stats descriptives (réel) des prix de ``gpu_model``, bornées au point-in-time."""
    return service.summary_stats(_STORE, gpu_model, lease_type=lease_type, as_of=as_of)


@mcp.tool()
def query(sql: str) -> dict[str, Any]:
    """SQL DuckDB **brut** sur la vue ``prices`` (le lac). Aucun garde point-in-time."""
    return service.run_query(_STORE, sql)


if __name__ == "__main__":
    mcp.run()
