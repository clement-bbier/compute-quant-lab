"""Tests des statistiques de dispersion inter-venues (mesure, pas signal de timing)."""

from __future__ import annotations

import datetime as dt

import pytest

from benchmark.dispersion import dispersion_at, venue_levels, venue_rates_at
from core.ingestion.compute_index import DEFAULT_INDEX_CONFIG, build_spot_index
from core.ingestion.protocols import Snapshot


def test_dispersion_matches_known_spread(two_day_snapshots, fix_day2) -> None:
    # Fix J : venues {vastai 2.10, runpod 2.30}, indice 2.20.
    d = dispersion_at(two_day_snapshots, fix_day2, "H100")
    assert d.n_venues == 2
    assert d.index_price == pytest.approx(2.20)
    assert d.spread_abs == pytest.approx(0.20)
    assert d.spread_pct == pytest.approx(0.20 / 2.20)
    assert d.cheapest_venue == "vastai"
    assert d.dearest_venue == "runpod"
    assert d.is_defined


def test_dispersion_cv_is_population_coefficient_of_variation(two_day_snapshots, fix_day2) -> None:
    # CV descriptif (écart-type population / moyenne) : std([2.10,2.30])=0.10, moyenne 2.20.
    d = dispersion_at(two_day_snapshots, fix_day2, "H100")
    assert d.cv == pytest.approx(0.10 / 2.20)


def test_single_venue_dispersion_is_undefined_but_priced(fix_day2) -> None:
    # Robustesse mono-venue (ex. H100 sur une seule marketplace) : pas de dispersion, flaggée.
    solo = [Snapshot(fix_day2 - dt.timedelta(hours=1), "vastai", "H100", 2.0)]
    d = dispersion_at(solo, fix_day2, "H100")
    assert d.n_venues == 1
    assert not d.is_defined
    assert d.spread_abs is None and d.spread_pct is None and d.cv is None
    assert d.cheapest_venue is None and d.dearest_venue is None
    assert d.index_price == pytest.approx(2.0)


def test_no_lookahead_future_snapshot_does_not_change_dispersion(
    two_day_snapshots, fix_day2
) -> None:
    leak = Snapshot(fix_day2 + dt.timedelta(hours=3), "newbie", "H100", 0.01)
    base = dispersion_at(two_day_snapshots, fix_day2, "H100")
    after = dispersion_at([*two_day_snapshots, leak], fix_day2, "H100")
    assert after.spread_abs == pytest.approx(base.spread_abs)
    assert after.n_venues == base.n_venues


def test_venue_rates_estimator_reproduces_index_price(two_day_snapshots, fix_day2) -> None:
    # Invariant anti-dérive : l'agrégation de mes venue_rates == prix de l'indice canonique.
    cfg = DEFAULT_INDEX_CONFIG
    rates = venue_rates_at(two_day_snapshots, fix_day2, "H100", config=cfg)
    kept = cfg.outlier_filter.filter(rates)
    canonical = build_spot_index(two_day_snapshots, fix_day2, "H100", config=cfg)
    assert cfg.estimator.estimate(kept) == pytest.approx(canonical.price_usd_per_hour)


def test_venue_levels_report_named_average_discount(two_day_snapshots, fix_day1, fix_day2) -> None:
    # Mesure descriptive « qui est moins cher » sur la fenêtre (PAS un signal de timing live).
    levels = {lv.source: lv for lv in venue_levels(two_day_snapshots, [fix_day1, fix_day2], "H100")}
    assert set(levels) == {"vastai", "runpod"}
    # vastai : rates 2.00 (fix J-1), 2.10 (fix J) → moyenne 2.05.
    assert levels["vastai"].mean_rate == pytest.approx(2.05)
    assert levels["runpod"].mean_rate == pytest.approx(2.25)
    # Escompte moyen par-fix vs indice : vastai sous l'indice, runpod au-dessus.
    expected_vastai = ((2.00 - 2.10) / 2.10 + (2.10 - 2.20) / 2.20) / 2
    assert levels["vastai"].mean_discount_vs_index == pytest.approx(expected_vastai)
    assert levels["vastai"].mean_discount_vs_index < 0 < levels["runpod"].mean_discount_vs_index
    assert levels["vastai"].n_fixes == 2
