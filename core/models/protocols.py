"""Contracts of the ML model layer (SOLID / Dependency Inversion).

The validation (`validation.py`) and the strategy adapter (`strategy.py`) depend on these
``Protocol`` classes — never on a concrete implementation. A new model (XGBoost today,
LSTM/TFT at the institutional tier) conforms to the `Model` contract and becomes usable
everywhere without changing the validation machinery (Open/Closed).

Target convention
-----------------
The target is **binary directional**: ``1`` = the spread rises over the horizon, ``0`` = it
falls (see `pipeline.build_labels`). A `Model` therefore exposes ``predict_proba`` returning
the probability ``P(up)`` per sample, in ``[0, 1]``.
"""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

#: Re-exported from :mod:`core.utils.types` so the public alias names are unchanged.
from core.utils.types import FloatArray, IntArray


@runtime_checkable
class Model(Protocol):
    """Injectable directional classifier: ``fit`` then ``predict_proba`` in [0, 1]."""

    def fit(self, x: FloatArray, y: FloatArray) -> "Model":
        """Train the model on ``(x, y)`` and return ``self`` (chaining)."""
        ...

    def predict_proba(self, x: FloatArray) -> FloatArray:
        """Probability ``P(up)`` per row of ``x`` (1-D vector in [0, 1])."""
        ...


@runtime_checkable
class Splitter(Protocol):
    """Generate temporal ``(train_idx, test_idx)`` splits (never shuffled)."""

    def split(self, n_samples: int) -> Iterator[tuple[IntArray, IntArray]]:
        """Iterate the folds: disjoint training and test indices."""
        ...


__all__ = ["FloatArray", "IntArray", "Model", "Splitter"]
