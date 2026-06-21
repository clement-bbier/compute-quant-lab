"""Modèle directionnel XGBoost + ensemble de graines (déterminisme, apprentissage).

Le déterminisme est non négociable (reproductibilité du labo) : même graine ⇒ mêmes
probabilités, bit pour bit. L'ensemble de graines moyenne les probabilités de membres
identiques sauf la graine — c'est l'« ensemble » du PoC (réduction de variance).
"""

from __future__ import annotations

import numpy as np

from core.models.protocols import Model
from core.models.xgboost_model import SeedBaggingEnsemble, XGBoostDirectionModel


def test_conforms_to_model_protocol() -> None:
    model = XGBoostDirectionModel(random_state=0)
    assert isinstance(model, Model)


def test_predictions_are_deterministic(predictable_dataset) -> None:
    x, y = predictable_dataset
    a = XGBoostDirectionModel(random_state=7).fit(x, y).predict_proba(x)
    b = XGBoostDirectionModel(random_state=7).fit(x, y).predict_proba(x)
    assert np.array_equal(a, b)


def test_proba_is_a_vector_in_unit_interval(predictable_dataset) -> None:
    x, y = predictable_dataset
    proba = XGBoostDirectionModel(random_state=0).fit(x, y).predict_proba(x)
    assert proba.shape == (x.shape[0],)
    assert proba.min() >= 0.0 and proba.max() <= 1.0


def test_learns_predictable_signal(predictable_dataset) -> None:
    x, y = predictable_dataset
    proba = XGBoostDirectionModel(random_state=0).fit(x, y).predict_proba(x)
    accuracy = float(((proba > 0.5).astype(float) == y).mean())
    assert accuracy > 0.65


def test_ensemble_averages_member_probabilities(predictable_dataset) -> None:
    x, y = predictable_dataset
    seeds = (1, 2, 3)
    ensemble = SeedBaggingEnsemble(
        make_model=lambda s: XGBoostDirectionModel(random_state=s, n_estimators=30),
        seeds=seeds,
    ).fit(x, y)
    members = [
        XGBoostDirectionModel(random_state=s, n_estimators=30).fit(x, y).predict_proba(x)
        for s in seeds
    ]
    expected = np.mean(members, axis=0)
    assert np.allclose(ensemble.predict_proba(x), expected)


def test_ensemble_conforms_to_model_protocol() -> None:
    ensemble = SeedBaggingEnsemble(
        make_model=lambda s: XGBoostDirectionModel(random_state=s), seeds=(1, 2)
    )
    assert isinstance(ensemble, Model)
