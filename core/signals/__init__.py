"""Reusable signal producers (lab foundation).

*PoC to foundation* promotion: signal logic from research projects moves up here, behind a
common interface (`SignalProducer`) compatible with the P08 backtest engine.

- `MeanReversionSignal` — spread mean reversion (hysteresis z-score, promoted from P02).
- `FuturesBasisSignal` — carry/roll of the future/spot basis (on top of the P06 cost-of-carry).
- `MLEnsembleSignal` — out-of-sample ML directional signal (wraps the P09 adapter).
"""

from core.signals.futures_basis import FuturesBasisSignal
from core.signals.mean_reversion import MeanReversionSignal
from core.signals.ml import MLEnsembleSignal
from core.signals.protocols import SignalProducer, SignalProvenance, clip_unit

__all__ = [
    "SignalProducer",
    "SignalProvenance",
    "clip_unit",
    "MeanReversionSignal",
    "FuturesBasisSignal",
    "MLEnsembleSignal",
]
