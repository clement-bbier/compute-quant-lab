"""Cold-store consumer run: DuckDB EDA plus MLflow logging (reproducibility).

Demonstrates the core of the batch (roadmap section 0, instance section 7): a consumer
reads the versioned Parquet lake through DuckDB and logs the run via
``core.utils.tracking``, whose git SHA pins the exact dataset. The same query is
therefore replayable months later against the same data version.

``summarize`` is a pure function (testable, no MLflow); ``main`` wraps it in an MLflow
run and materialises ``results/run_summary.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.duckdb_query import query
from core.storage.parquet_store import ParquetPriceStore
from core.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)

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
    """Audit statistics of the lake via DuckDB (pure, no side effect).

    Returns
    -------
    dict
        ``n_rows``, ``n_sources``, ``n_models`` (integers) plus ``min_price`` /
        ``max_price`` (floats, $/GPU-h). All zero on an empty lake.
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
    """MLflow run: log the cold-store statistics and write ``run_summary.json``.

    Imports MLflow lazily so that ``summarize`` stays testable without the dependency.
    """
    import mlflow

    from core.utils import tracking

    store = store or ParquetPriceStore(SNAPSHOT_DIR)
    summary = summarize(store)
    with tracking.run("storage_cold_store", {"backend": "parquet", "engine": "duckdb"}):
        mlflow.log_metrics({k: float(v) for k, v in summary.items()})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Cold store summary: %s", summary)
    return summary


if __name__ == "__main__":
    configure_logging()
    main()
