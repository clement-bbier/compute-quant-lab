"""Tests d'intégration de la construction d'indice spot (point-in-time + configurable)."""

from __future__ import annotations

import datetime as dt

import pytest

from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    build_spot_index,
)
from core.ingestion.estimators import AvailabilityWeightedMean, MadOutlierFilter
from core.ingestion.protocols import Snapshot


def test_default_index_matches_market_standard(index_snapshots, as_of) -> None:
    pt = build_spot_index(index_snapshots, as_of, "H100")
    # 4 venues retenues [2.00, 2.10, 2.20, 2.30] -> trimmed mean (k=0) = 2.15
    assert pt.price_usd_per_hour == pytest.approx(2.15)
    assert pt.n_sources == 4
    assert pt.method == "trimmed_mean20+mad2.5"
    assert pt.gpu_model == "H100"
    assert pt.lease_type == "on_demand"


def test_oldest_retained_observation_is_tracked(index_snapshots, as_of) -> None:
    pt = build_spot_index(index_snapshots, as_of, "H100")
    # coreweave à as_of - 3 h est le plus vieux relevé conservé (auditabilité staleness)
    assert pt.oldest_obs_at == as_of - dt.timedelta(hours=3)


def test_no_lookahead_future_observation_ignored(index_snapshots, as_of) -> None:
    # Une observation postérieure à as_of ne doit jamais modifier le fix (point-in-time).
    leak = Snapshot(as_of + dt.timedelta(hours=2), "vastai", "H100", 100.0)
    base = build_spot_index(index_snapshots, as_of, "H100")
    after = build_spot_index([*index_snapshots, leak], as_of, "H100")
    assert after.price_usd_per_hour == base.price_usd_per_hour == pytest.approx(2.15)


def test_stale_venue_not_carried_forward(as_of) -> None:
    # No carry-forward : une venue dont le seul relevé est périmé est ignorée.
    fresh = Snapshot(as_of - dt.timedelta(hours=1), "vastai", "H100", 2.0)
    stale = Snapshot(as_of - dt.timedelta(hours=30), "old", "H100", 1.5)
    pt = build_spot_index([fresh, stale], as_of, "H100")
    assert pt.n_sources == 1
    assert pt.price_usd_per_hour == pytest.approx(2.0)


def test_insufficient_data_raises(as_of) -> None:
    only_stale = [Snapshot(as_of - dt.timedelta(hours=30), "old", "H100", 1.5)]
    with pytest.raises(InsufficientDataError):
        build_spot_index(only_stale, as_of, "H100")


def test_estimator_is_configurable(index_snapshots, as_of) -> None:
    # Même pipeline, estimateur permuté par injection -> résultat et méthode différents.
    cfg = IndexConfig(estimator=AvailabilityWeightedMean(), outlier_filter=MadOutlierFilter(2.5))
    pt = build_spot_index(index_snapshots, as_of, "H100", config=cfg)
    # (2.00*100 + 2.20*50 + 2.10*200 + 2.30*10) / 360 = 753/360
    assert pt.price_usd_per_hour == pytest.approx(753 / 360)
    assert pt.price_usd_per_hour != pytest.approx(2.15)
    assert pt.method == "avail_weighted+mad2.5"


def test_default_config_is_market_standard() -> None:
    assert DEFAULT_INDEX_CONFIG.method == "trimmed_mean20+mad2.5"
    assert DEFAULT_INDEX_CONFIG.staleness == dt.timedelta(hours=24)
    assert "aws" in DEFAULT_INDEX_CONFIG.excluded_sources


def test_intra_venue_distribution_aggregated_not_arbitrary(as_of) -> None:
    # Une venue avec N offres au MÊME timestamp -> médiane robuste de la cohorte,
    # jamais une offre prise au hasard (le bug corrigé). 100.0 est un outlier intra-venue.
    ts = as_of - dt.timedelta(hours=1)
    offers = [
        Snapshot(ts, "vastai", "H100", 2.0, "on_demand", 1),
        Snapshot(ts, "vastai", "H100", 2.2, "on_demand", 1),
        Snapshot(ts, "vastai", "H100", 100.0, "on_demand", 1),
        Snapshot(ts, "runpod", "H100", 2.4, "on_demand", 1),
    ]
    pt = build_spot_index(offers, as_of, "H100")
    # vastai -> median(2.0, 2.2, 100) = 2.2 ; runpod -> 2.4 ; 2 venues ; trimmed(k=0) = 2.3
    assert pt.n_sources == 2
    assert pt.price_usd_per_hour == pytest.approx(2.3)


def test_intra_venue_availability_is_summed(as_of) -> None:
    # La disponibilité d'une venue agrège tout son carnet (somme), pas une offre.
    from core.ingestion.estimators import AvailabilityWeightedMean, NoOutlierFilter

    ts = as_of - dt.timedelta(hours=1)
    offers = [
        Snapshot(ts, "vastai", "H100", 2.0, "on_demand", 3),
        Snapshot(ts, "vastai", "H100", 2.0, "on_demand", 5),
        Snapshot(ts, "runpod", "H100", 4.0, "on_demand", 2),
    ]
    cfg = IndexConfig(estimator=AvailabilityWeightedMean(), outlier_filter=NoOutlierFilter())
    pt = build_spot_index(offers, as_of, "H100", config=cfg)
    # vastai dispo=8 @2.0, runpod dispo=2 @4.0 -> (2*8 + 4*2)/10 = 2.4
    assert pt.price_usd_per_hour == pytest.approx(2.4)
