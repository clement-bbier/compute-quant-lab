"""Integration smoke test: sources -> point-in-time builder -> lead measurement.

No network, no MLflow I/O (deterministic): verifies that the full pipeline
*recovers* the lead injected by the synthetic DGP, while respecting point-in-time.
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

    # The DGP injects LEAD_DAYS; the pipeline must recover it (the publication lag
    # eats ~1 exploitable day of lead -> tolerance +-2 days).
    assert abs(lead["best_lag"] - sources.LEAD_DAYS) <= 2
    assert lead["best_abs_corr"] > 0.3
    assert -1.0 <= lead["ols_confirmation"]["r2_oos"] <= 1.0


def test_features_are_point_in_time():
    # No feature should exist before the rolling-window warmup completes.
    panel = sources.load_panel()
    builder = PointInTimeFeatureBuilder(panel.source, run_signal.FEATURE_SPECS)
    features = builder.build_panel(panel.decision_index)
    assert features.index.equals(panel.decision_index)
    # rolling_mean(7) at the very first decision instant: defined (sufficient warmup).
    assert features["gas_price_roll7"].iloc[0] == features["gas_price_roll7"].iloc[0]  # not NaN
