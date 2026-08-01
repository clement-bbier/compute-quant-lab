"""Capstone test: calibration distinguishes real signal from noise (L0 §7)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ercot_calibration import run_calibration


def test_run_calibration_distinguishes_signal_from_noise() -> None:
    rng = np.random.default_rng(0)
    n = 600
    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    feat = rng.random(n)
    # Label A: depends on the predictor (signal exploitable beyond climatology).
    y_signal = (feat + rng.random(n) * 0.3 > 1.0).astype(np.float64)
    # Label B: noise independent of the predictor, same base rate.
    y_noise = (rng.random(n) < float(y_signal.mean())).astype(np.float64)
    x = feat.reshape(-1, 1)

    res = run_calibration(x, index, {"A_signal": y_signal, "B_noise": y_noise}, n_boot=200, seed=1)

    # The real signal beats the baseline and survives the multiplicity correction.
    assert res["A_signal"]["beats"] is True
    assert res["A_signal"]["bh_significant"] is True
    # Noise does not pass (false-positive guard).
    assert res["B_noise"]["bh_significant"] is False
