"""Noyau vectoriel de référence du spread (pur numpy).

C'est l'implémentation *canonique* du `SpreadKernel` : l'oracle contre lequel la
parité du noyau Rust est testée. Pur, sans I/O, sans état — substituable au Rust
par simple injection dans le pricer.
"""

from __future__ import annotations

from core.pricing.protocols import FloatArray

KWH_PER_MWH: float = 1000.0


class PythonOracle:
    """Noyau Python de référence (implémente `SpreadKernel`)."""

    def compute(
        self,
        compute_eur_per_gpu_h: FloatArray,
        energy_eur_per_mwh: FloatArray,
        power_kw_per_gpu: FloatArray,
        pue: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Calcule ``(revenu, coût, spread)`` élément par élément.

        Le coût énergétique d'une heure-GPU vaut
        ``power_kw · pue · (€/MWh) / 1000`` : la puissance IT (kW), majorée par
        le PUE pour le refroidissement, consommée pendant une heure (kWh), au
        prix de l'électricité ramené en €/kWh.
        """
        revenue = compute_eur_per_gpu_h
        cost = power_kw_per_gpu * pue * energy_eur_per_mwh / KWH_PER_MWH
        spread = revenue - cost
        return revenue, cost, spread
