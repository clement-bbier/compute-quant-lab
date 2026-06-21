"""Fixtures et chemins des tests P06 (futures compute théoriques).

Le cœur du pricing vit dans ``core.pricing.derivatives`` (paquet installé en
editable, importable directement). Ce conftest rend en plus importables :
  - le code projet sous ``projects/06_compute_futures_pricing/src`` (adapter P04) ;
  - le paquet ``forward`` de P04 sous ``projects/04_compute_index_curve/src``
    (courbe forward SIMULÉE servant à la cohérence carry ↔ Schwartz).
"""

from __future__ import annotations

import sys
from pathlib import Path

_P06_SRC = Path(__file__).resolve().parents[1] / "src"
_P04_SRC = Path(__file__).resolve().parents[2] / "04_compute_index_curve" / "src"
for _path in (_P06_SRC, _P04_SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
