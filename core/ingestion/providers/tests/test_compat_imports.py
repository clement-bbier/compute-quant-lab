"""Compatibility: the legacy import paths stay valid (anti-breakage).

The ``core.ingestion.gpu_market`` shim and the ``core.ingestion`` facade must keep exposing
the same public symbols -- otherwise existing importers (the collector, the facade, the P04
tests) would break.
"""

from __future__ import annotations


def test_legacy_imports_from_gpu_market_still_work() -> None:
    from core.ingestion.gpu_market import (
        fetch_live_gpu_prices,
        fetch_runpod,
        fetch_vastai,
        normalize_gpu_model,
        parse_runpod_gpu_types,
        parse_vastai_offers,
    )

    assert all(
        callable(fn)
        for fn in (
            fetch_live_gpu_prices,
            fetch_runpod,
            fetch_vastai,
            normalize_gpu_model,
            parse_runpod_gpu_types,
            parse_vastai_offers,
        )
    )


def test_package_facade_reexports_still_work() -> None:
    # core.ingestion.__init__ re-exports from gpu_market: must stay importable.
    from core.ingestion import (
        fetch_live_gpu_prices,
        normalize_gpu_model,
        parse_vastai_offers,
    )

    assert callable(fetch_live_gpu_prices)
    assert callable(normalize_gpu_model)
    assert callable(parse_vastai_offers)
