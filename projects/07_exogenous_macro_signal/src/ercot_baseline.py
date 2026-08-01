"""ERCOT climatology baseline (L0 spec §7) — the "thing to beat".

Base spike rate by (hour-of-day x month). A signal is only kept if it
**beats** this naive seasonality (otherwise it merely rediscovers that
summer afternoons are tight). Pure functions, fitted on the training fold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ClimatologyBaseline:
    """Base spike rate by (hour-of-day, month), + global fallback.

    Fitted on the training labels; predicts a probability per timestamp.
    """

    rates: dict[tuple[int, int], float]
    global_rate: float

    @classmethod
    def fit(cls, labels: pd.Series) -> ClimatologyBaseline:
        """Fits the base rate by (hour, month) on ``labels`` (bool/0-1, UTC index)."""
        if labels.index.tz is None:
            raise ValueError("UTC tz-aware index required")
        frame = pd.DataFrame(
            {
                "y": labels.to_numpy(dtype=float),
                "hour": np.asarray(labels.index.hour),
                "month": np.asarray(labels.index.month),
            }
        )
        rates = frame.groupby(["hour", "month"])["y"].mean().to_dict()
        return cls(rates=dict(rates), global_rate=float(frame["y"].mean()))

    def predict(self, index: pd.DatetimeIndex) -> np.ndarray:
        """Spike probability per timestamp: (hour, month) rate, global fallback if unknown."""
        return np.array(
            [self.rates.get((t.hour, t.month), self.global_rate) for t in index],
            dtype=float,
        )
