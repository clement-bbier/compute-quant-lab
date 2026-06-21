"""Run consommateur du cold store : EDA DuckDB + log de la version DVC (reproductibilité).

Démontre le **cœur du lot** (roadmap §0, instance §7) : un consommateur lit le lac Parquet
versionné via DuckDB et logge la **version DVC** des données (par ``core.utils.tracking``),
si bien qu'une même requête est rejouable des mois plus tard sur la même version de données.

``summarize`` est une fonction pure (testable, sans MLflow) ; ``main`` l'enveloppe d'un run
MLflow et matérialise ``results/run_summary.json``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.storage.duckdb_query import query
from core.storage.parquet_store import ParquetPriceStore

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

_SUMMARY_SQL = """
SELECT
    COUNT(*)                     AS n_rows,
    COUNT(DISTINCT source)       AS n_sources,
    COUNT(DISTINCT gpu_model)    AS n_models,
    COALESCE(MIN(price_usd_per_hour), 0.0) AS min_price,
    COALESCE(MAX(price_usd_per_hour), 0.0) AS max_price
FROM prices
"""


def summarize(store: ParquetPriceStore) -> dict[str, Any]:
    """Statistiques d'audit du lac via DuckDB (pure, sans effet de bord).

    Returns
    -------
    dict
        ``n_rows``, ``n_sources``, ``n_models`` (entiers) et ``min_price`` / ``max_price``
        (flottants $/GPU·h). Tout à zéro sur un lac vide.
    """
    row = query(_SUMMARY_SQL, store).iloc[0]
    return {
        "n_rows": int(row["n_rows"]),
        "n_sources": int(row["n_sources"]),
        "n_models": int(row["n_models"]),
        "min_price": float(row["min_price"]),
        "max_price": float(row["max_price"]),
    }


def main(store: ParquetPriceStore | None = None) -> dict[str, Any]:
    """Run MLflow : logge les stats du cold store + la version DVC, écrit ``run_summary.json``.

    Importe MLflow paresseusement pour que ``summarize`` reste testable sans la dépendance.
    """
    from core.utils import tracking  # import paresseux (effets de bord MLflow)
    import mlflow

    store = store or ParquetPriceStore(SNAPSHOT_DIR)
    summary = summarize(store)
    with tracking.run("storage_cold_store", {"backend": "parquet", "engine": "duckdb"}):
        mlflow.log_metrics({k: float(v) for k, v in summary.items()})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Cold store résumé : %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
