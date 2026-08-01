"""Makes the code in ``src/`` importable by the tests (unpackaged folder)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
