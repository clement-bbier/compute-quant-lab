"""Jambe compute du labo : ingestion des prix GPU et construction de l'indice spot.

Expose les types, protocoles, stratégies d'agrégation et le constructeur d'indice. Le
détail des sources réelles (marketplace) vit dans ``gpu_market.py``, le stockage dans
``snapshot_store.py``, l'agrégation configurable dans ``estimators.py`` / ``compute_index.py``.
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
    # Sous-paquets de connecteurs (façade symétrique : compute + énergie).
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
