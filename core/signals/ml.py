"""Out-of-sample ML directional signal (wraps the P09 adapter).

The producer **delegates** to ``PrecomputedSignalStrategy`` from ``core.models`` (P09): a vector
of out-of-sample ``P(up)`` probabilities (purged-CV, see ``core.models.validation.oos_predict``)
is computed **upstream** and aligned 1:1 with the backtested series; at runtime the adapter reads
the probability at ``view.t`` and maps it to a position (neutral band around 0.5). The model
never sees prices at runtime — any potential leakage was neutralised at training time.

So **no** signal logic is added here: exact parity with P09 is guaranteed by delegation (section
6b). This module only provides the ``SignalProducer`` wrapping (name + real/simulated provenance).
"""

from __future__ import annotations

from core.backtest.protocols import PointInTimeView
from core.models.protocols import FloatArray
from core.models.strategy import PrecomputedSignalStrategy
from core.signals.protocols import SignalProvenance


class MLEnsembleSignal:
    """``SignalProducer`` wrapper around the precomputed ML adapter of P09.

    Parameters
    ----------
    proba : FloatArray
        OOS ``P(up)`` vector aligned with the backtested series (``NaN`` gives a flat position).
    neutral_band : float
        Half-width of the dead band around 0.5 (``[0, 0.5)``), passed through as-is to P09.
    name : str
        Signal identifier (MLflow tracking / desk attribution).
    simulated : bool
        **Mandatory** real/simulated flag (rule ``forward-real-simulated``).
    """

    def __init__(
        self,
        proba: FloatArray,
        *,
        neutral_band: float = 0.0,
        name: str = "ml_ensemble",
        simulated: bool,
    ) -> None:
        # Validation (neutral band) and probability-to-position logic inherited as-is from P09.
        self._strategy = PrecomputedSignalStrategy(proba, neutral_band=neutral_band)
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=simulated)

    def signal(self, view: PointInTimeView) -> float:
        """Target position at ``view.t``: delegates to the P09 adapter (exact parity)."""
        return self._strategy.signal(view)


__all__ = ["MLEnsembleSignal"]
