"""Test capstone : la calibration distingue un vrai signal d'un bruit (L0 §7)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ercot_calibration import run_calibration


def test_run_calibration_distinguishes_signal_from_noise() -> None:
    rng = np.random.default_rng(0)
    n = 600
    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    feat = rng.random(n)
    # Label A : dépend du prédicteur (signal exploitable hors climatologie).
    y_signal = (feat + rng.random(n) * 0.3 > 1.0).astype(np.float64)
    # Label B : bruit indépendant du prédicteur, même taux de base.
    y_noise = (rng.random(n) < float(y_signal.mean())).astype(np.float64)
    x = feat.reshape(-1, 1)

    res = run_calibration(x, index, {"A_signal": y_signal, "B_noise": y_noise}, n_boot=200, seed=1)

    # Le vrai signal bat la baseline et survit à la correction de multiplicité.
    assert res["A_signal"]["beats"] is True
    assert res["A_signal"]["bh_significant"] is True
    # Le bruit ne passe pas (garde-fou anti-faux-positif).
    assert res["B_noise"]["bh_significant"] is False
