"""L0 §7 evaluation — threshold-free PR-AUC + "does it beat the baseline?" + Benjamini-Hochberg.

*Policy-free* metric (signal quality is measured without a threshold or cost; cost
asymmetry is a downstream decision, out of scope for L0). L0 decision: the signal is
kept if its PR-AUC beats the climatology baseline in the sense of a bootstrap CI,
after Benjamini-Hochberg multiplicity correction over the spec budget.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score


def pr_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    """Threshold-free PR-AUC (average precision)."""
    return float(average_precision_score(y_true, score))


def beats_baseline(
    y_true: np.ndarray,
    score_model: np.ndarray,
    score_baseline: np.ndarray,
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, float | bool]:
    """Does the model beat the baseline? PR-AUC + bootstrap CI + p-value of the difference.

    Resamples (with replacement) the model-minus-baseline PR-AUC difference. L0
    decision: ``beats`` is true if the lower bound of the 95% CI of the difference is > 0.
    """
    y_true = np.asarray(y_true)
    score_model = np.asarray(score_model, dtype=float)
    score_baseline = np.asarray(score_baseline, dtype=float)
    n = len(y_true)
    rng = np.random.default_rng(seed)

    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y_true[idx]
        if yb.sum() == 0 or yb.sum() == len(yb):  # degenerate resample (single class)
            continue
        diffs.append(
            average_precision_score(yb, score_model[idx])
            - average_precision_score(yb, score_baseline[idx])
        )
    arr = np.asarray(diffs, dtype=float)
    lo, hi = (float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975)))
    p_value = float((arr <= 0.0).mean())  # H0: model does not beat the baseline
    return {
        "pr_auc_model": pr_auc(y_true, score_model),
        "pr_auc_baseline": pr_auc(y_true, score_baseline),
        "diff_ci_low": lo,
        "diff_ci_high": hi,
        "p_value": p_value,
        "beats": bool(lo > 0.0),
    }


def benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg rejection (FDR ``alpha``); rejection mask in input order.

    Controls the false discovery rate over the L0 spec budget (multiplicity
    correction). Returns ``True`` for each rejected (= significant) spec.
    """
    p = np.asarray(pvalues, dtype=float)
    m = p.size
    if m == 0:
        return []
    order = np.argsort(p)
    thresholds = alpha * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresholds
    kmax = int(np.max(np.where(passed)[0])) + 1 if passed.any() else 0
    reject = np.zeros(m, dtype=bool)
    if kmax > 0:
        reject[order[:kmax]] = True
    return reject.tolist()
