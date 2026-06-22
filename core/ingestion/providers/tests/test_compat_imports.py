"""Compat : les imports legacy restent valides après le refactor (anti-casse).

Le shim ``core.ingestion.gpu_market`` et la façade ``core.ingestion`` (NON modifiée, hors
module possédé) doivent continuer d'exposer les mêmes symboles publics — sans quoi des
importateurs existants (collecteur, façade, tests P04) casseraient.
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
    # core.ingestion.__init__ ré-exporte depuis gpu_market : doit rester importable.
    from core.ingestion import (
        fetch_live_gpu_prices,
        normalize_gpu_model,
        parse_vastai_offers,
    )

    assert callable(fetch_live_gpu_prices)
    assert callable(normalize_gpu_model)
    assert callable(parse_vastai_offers)
