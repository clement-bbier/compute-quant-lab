"""Évaluation L0 §7 — PR-AUC threshold-free + « bat-il la baseline ? » + Benjamini-Hochberg.

Métrique *policy-free* (la qualité de signal se mesure sans seuil ni coût ; l'asymétrie
de coût est une décision aval, hors L0). Décision L0 : le signal est retenu si sa PR-AUC
dépasse la baseline climatologique au sens d'un IC bootstrap, après correction de
multiplicité Benjamini-Hochberg sur le budget de specs.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score


def pr_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    """PR-AUC (average precision) threshold-free."""
    return float(average_precision_score(y_true, score))


def beats_baseline(
    y_true: np.ndarray,
    score_model: np.ndarray,
    score_baseline: np.ndarray,
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, float | bool]:
    """Le modèle bat-il la baseline ? PR-AUC + IC bootstrap + p-value de la différence.

    Rééchantillonne (avec remise) la différence de PR-AUC modèle − baseline. Décision
    L0 : ``beats`` vrai si la borne basse de l'IC 95 % de la différence est > 0.
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
        if yb.sum() == 0 or yb.sum() == len(yb):  # resample dégénéré (une classe)
            continue
        diffs.append(
            average_precision_score(yb, score_model[idx])
            - average_precision_score(yb, score_baseline[idx])
        )
    arr = np.asarray(diffs, dtype=float)
    lo, hi = (float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975)))
    p_value = float((arr <= 0.0).mean())  # H0 : modèle ne bat pas la baseline
    return {
        "pr_auc_model": pr_auc(y_true, score_model),
        "pr_auc_baseline": pr_auc(y_true, score_baseline),
        "diff_ci_low": lo,
        "diff_ci_high": hi,
        "p_value": p_value,
        "beats": bool(lo > 0.0),
    }


def benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    """Rejet Benjamini-Hochberg (FDR ``alpha``) ; masque de rejet dans l'ordre d'entrée.

    Contrôle le taux de fausses découvertes sur le budget de specs L0 (correction de
    multiplicité). Renvoie ``True`` pour chaque spec rejetée (= significative).
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
