"""Fixtures déterministes des tests P10 (desk : portefeuille + exécution).

On prouve la pondération, les coûts d'exécution, l'anti look-ahead et le PnL net sur des
cas analytiques **avant** de brancher les vrais signaux (P02/P06/P09, en convergence).
Graine fixée partout → reproductible (rule ``quant-no-lookahead``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Rend les modules du projet (sous src/) importables dans les tests, comme P02/P04.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Graine unique de tout l'aléatoire des fixtures (reproductibilité).
SEED: int = 42


@pytest.fixture
def desk_prices() -> np.ndarray:
    """Série de prix desk synthétique *positive* (marche aléatoire bornée), float64.

    Sert de sous-jacent unique du desk : les signaux mockés s'y appliquent via la
    ``GuardedView`` de P08. Strictement simulée.
    """
    rng = np.random.default_rng(SEED)
    n = 256
    prices = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    return np.clip(prices, 1.0, None).astype(np.float64)
