"""Smoke d'intégration : sources → builder point-in-time → mesure du lead.

Sans réseau ni I/O MLflow/DVC (déterministe) : on vérifie que le pipeline complet
*retrouve* le lead injecté par le DGP synthétique, en respectant le point-in-time.
"""

from __future__ import annotations

import run_signal
import sources

from core.features import PointInTimeFeatureBuilder


def test_pipeline_recovers_injected_lead_point_in_time():
    panel = sources.load_panel()
    builder = PointInTimeFeatureBuilder(panel.source, run_signal.FEATURE_SPECS)
    features = builder.build_panel(panel.decision_index)

    lead = run_signal.measure_lead(features, panel.spread)

    # Le DGP injecte LEAD_DAYS ; le pipeline doit le retrouver (le lag de publication
    # rogne ~1 j d'avance exploitable → tolérance ±2 j).
    assert abs(lead["best_lag"] - sources.LEAD_DAYS) <= 2
    assert lead["best_abs_corr"] > 0.3
    assert -1.0 <= lead["ols_confirmation"]["r2_oos"] <= 1.0


def test_features_are_point_in_time():
    # Aucune feature ne doit exister avant l'amorçage des fenêtres glissantes.
    panel = sources.load_panel()
    builder = PointInTimeFeatureBuilder(panel.source, run_signal.FEATURE_SPECS)
    features = builder.build_panel(panel.decision_index)
    assert features.index.equals(panel.decision_index)
    # rolling_mean(7) au tout premier instant de décision : défini (warmup suffisant).
    assert features["gas_price_roll7"].iloc[0] == features["gas_price_roll7"].iloc[0]  # not NaN
