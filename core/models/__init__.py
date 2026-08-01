"""The lab's ML model layer (Strategy layer, P09).

Directional ensemble on the spark spread, **backtestable through the P08 `Strategy`
interface** without glue: an out-of-sample probability vector (purged CV) becomes a position
signal. Central discipline: the rigor of temporal validation (anti-overfitting) outweighs
model complexity.

Reusable building blocks:
  - `protocols`   : `Model` / `Splitter` contracts (DI).
  - `validation`  : `PurgedKFold` (+embargo), `oos_predict`, `deflated_sharpe_ratio`.
  - `pipeline`    : `FeaturePipeline` (consumes `core.features` P07), `build_labels`.
  - `xgboost_model` : `XGBoostDirectionModel`, `SeedBaggingEnsemble`.
  - `strategy`    : `PrecomputedSignalStrategy` (adapter towards `core.backtest`).
"""

from typing import TYPE_CHECKING, Any

from core.models.pipeline import FeaturePipeline, SpreadFeatureSpec, build_labels
from core.models.protocols import FloatArray, IntArray, Model, Splitter
from core.models.validation import (
    PurgedKFold,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    oos_predict,
)
from core.models.xgboost_model import SeedBaggingEnsemble, XGBoostDirectionModel

if TYPE_CHECKING:
    from core.models.strategy import PrecomputedSignalStrategy


def __getattr__(name: str) -> Any:
    """Lazy import of the backtest adapter.

    `strategy` pulls in `core.backtest` (Rust kernel). It is loaded on demand so that
    `import core.models` (or its pure `validation`/`pipeline` utilities) does not depend on
    the Rust build — decoupling the pure blocks from the backtest adapter.
    """
    if name == "PrecomputedSignalStrategy":
        from core.models.strategy import PrecomputedSignalStrategy

        return PrecomputedSignalStrategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Contracts.
    "Model",
    "Splitter",
    "FloatArray",
    "IntArray",
    # Temporal anti-overfitting validation.
    "PurgedKFold",
    "oos_predict",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
    # Features & target.
    "FeaturePipeline",
    "SpreadFeatureSpec",
    "build_labels",
    # Models.
    "XGBoostDirectionModel",
    "SeedBaggingEnsemble",
    # Backtest adapter.
    "PrecomputedSignalStrategy",
]
