"""Tests de l'évaluation L0 §7 (PR-AUC, beats_baseline, Benjamini-Hochberg)."""

from __future__ import annotations

import numpy as np

from ercot_eval import beats_baseline, benjamini_hochberg, pr_auc


def test_pr_auc_perfect_ranking() -> None:
    y = np.array([0, 0, 1, 1])
    assert pr_auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0


def test_beats_baseline_when_model_informative() -> None:
    rng = np.random.default_rng(0)
    n = 500
    y = (rng.random(n) < 0.1).astype(int)  # ~10 % de spikes
    score_model = y * 0.7 + rng.random(n) * 0.3  # informatif
    score_baseline = np.full(n, 0.1)  # constant = taux de base
    res = beats_baseline(y, score_model, score_baseline, n_boot=300, seed=1)
    assert res["pr_auc_model"] > res["pr_auc_baseline"]
    assert res["beats"] is True  # IC de la différence > 0
    assert res["diff_ci_low"] > 0.0


def test_does_not_beat_when_model_uninformative() -> None:
    rng = np.random.default_rng(2)
    n = 500
    y = (rng.random(n) < 0.1).astype(int)
    noise = rng.random(n)  # aucun lien avec y
    res = beats_baseline(y, noise, np.full(n, 0.1), n_boot=300, seed=3)
    assert res["beats"] is False  # un bruit ne bat pas la baseline


def test_benjamini_hochberg_rejects_small_pvalues() -> None:
    # m=4, alpha=0.05 → seuils 0.0125/0.025/0.0375/0.05 ; rejette 0.001 et 0.02
    assert benjamini_hochberg([0.001, 0.5, 0.02, 0.8], alpha=0.05) == [True, False, True, False]


def test_benjamini_hochberg_empty() -> None:
    assert benjamini_hochberg([]) == []
