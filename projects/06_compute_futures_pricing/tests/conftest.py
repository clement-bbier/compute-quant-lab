"""Fixtures and paths for P06 tests (theoretical compute futures).

The pricing core lives in ``core.pricing.derivatives`` (package installed in
editable mode, directly importable). This conftest additionally makes importable:
  - the project code under ``projects/06_compute_futures_pricing/src`` (P04 adapter);
  - P04's ``forward`` package under ``projects/04_compute_index_curve/src``
    (SIMULATED forward curve used for carry ↔ Schwartz consistency).
"""

from __future__ import annotations

import sys
from pathlib import Path

_P06_SRC = Path(__file__).resolve().parents[1] / "src"
_P04_SRC = Path(__file__).resolve().parents[2] / "04_compute_index_curve" / "src"
for _path in (_P06_SRC, _P04_SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
