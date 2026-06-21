"""Vérifie que le pricing reproduit les chiffres de référence de la thèse."""

from core.pricing.spark_spread import (
    ServerSpec,
    energy_cost_per_gpu_hour,
    spark_spread_per_gpu_hour,
)


def test_energy_cost_matches_reference_figures():
    # 8x H100 @ 10.2 kW, 150 €/MWh -> ~1.53 €/h serveur, ~0.19 €/h/GPU
    cost_per_gpu = energy_cost_per_gpu_hour(150.0)
    assert round(cost_per_gpu, 2) == 0.19

    spec = ServerSpec()
    cost_server = cost_per_gpu * spec.n_gpus
    assert round(cost_server, 2) == 1.53


def test_spark_spread_sign():
    # Si le compute se vend 0.50 €/h/GPU et l'énergie coûte 0.19, marge positive.
    spread = spark_spread_per_gpu_hour(0.50, 150.0)
    assert spread > 0
    assert round(spread, 2) == 0.31


def test_negative_spread_when_energy_expensive():
    # Énergie chère -> produire du compute devient non rentable.
    spread = spark_spread_per_gpu_hour(0.20, 600.0)
    assert spread < 0
