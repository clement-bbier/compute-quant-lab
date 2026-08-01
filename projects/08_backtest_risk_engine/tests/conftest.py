"""pytest configuration for P08's own tests (the demo fixture strategy, not the engine).

The engine itself (``core.backtest``) is tested in ``core/backtest/tests``; this
directory only covers ``src/demo_fixtures.py``, which is local to this project.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
