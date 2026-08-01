"""Signal provenance: real vs simulated (non-negotiable boundary).

P12 **promoted** the canonical provenance into ``core.signals`` (reusable foundation). This module
**re-exports** it to stay backward-compatible (``from provenance import SignalProvenance``): a
single type shared between the PoC mocks and the real producers (P02/P06/P09), no duplication.

The ``simulated`` flag has **no default**: it's impossible to forget to label a signal (rule
``forward-real-simulated``). A mock PnL is never sold as alpha.
"""

from __future__ import annotations

from core.signals import SignalProvenance

__all__ = ["SignalProvenance"]
