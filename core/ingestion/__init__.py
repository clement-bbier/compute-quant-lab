"""Compute leg of the lab: GPU price ingestion and spot index construction.

Exposes the types, protocols, aggregation strategies and the index builder. The real
sources (marketplaces) live in ``gpu_market.py``, storage in ``snapshot_store.py``, and
the configurable aggregation in ``estimators.py`` / ``compute_index.py``.
"""

from core.ingestion import energy, providers
from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    HYPERSCALERS,
    IndexConfig,
    InsufficientDataError,
    MarketplaceProxySource,
    SiliconDataSource,
    build_spot_index,
)
from core.ingestion.estimators import (
    AvailabilityWeightedMean,
    MadOutlierFilter,
    Median,
    NoOutlierFilter,
    TrimmedMean,
)
from core.ingestion.gpu_market import (
    fetch_live_gpu_prices,
    normalize_gpu_model,
    parse_vastai_offers,
)
from core.ingestion.protocols import (
    ComputeIndexSource,
    IndexEstimator,
    OutlierFilter,
    Snapshot,
    SnapshotStore,
    SpotIndexPoint,
    VenueRate,
    ensure_utc,
)
from core.ingestion.snapshot_store import CsvSnapshotStore

__all__ = [
    # Connector subpackages (symmetric facade: compute + energy).
    "energy",
    "providers",
    "DEFAULT_INDEX_CONFIG",
    "HYPERSCALERS",
    "IndexConfig",
    "InsufficientDataError",
    "MarketplaceProxySource",
    "SiliconDataSource",
    "build_spot_index",
    "AvailabilityWeightedMean",
    "MadOutlierFilter",
    "Median",
    "NoOutlierFilter",
    "TrimmedMean",
    "fetch_live_gpu_prices",
    "normalize_gpu_model",
    "parse_vastai_offers",
    "ComputeIndexSource",
    "IndexEstimator",
    "OutlierFilter",
    "Snapshot",
    "SnapshotStore",
    "SpotIndexPoint",
    "VenueRate",
    "ensure_utc",
    "CsvSnapshotStore",
]
