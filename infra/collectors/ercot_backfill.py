"""Backfill ERCOT historique : API hébergée GridStatus.io → cold store énergie.

Tire le prix RTM + les prévisions (charge, capacité STSA, net-load) sur une plage, en
**format long point-in-time**, et les écrit dans :class:`EnergyColdStore` (Parquet, à
versionner ensuite via ``dvc add``). La calibration P07 lira ce lac immuable (rule
training-cold-store), jamais le live.

⚠️ Opérationnel : nécessite ``GRIDSTATUS_API_KEY``. **Quota** free = 500k lignes/mois →
borner la plage (étés à spikes) ou agréger ; vérifier la **profondeur d'archive des
prévisions** (le facteur limitant — cf. plan cold store).

Usage : ``uv run python -m infra.collectors.ercot_backfill`` (plage à régler dans ``main``).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.ingestion.energy.ercot import (
    parse_load_forecast,
    parse_net_load_forecast,
    parse_rtm_spp,
    parse_system_adequacy,
)
from core.ingestion.energy.ercot_transport import ErcotTransport, GridstatusIoTransport
from core.storage.energy_store import (
    INTERVAL_START,
    PUBLISH_TIME,
    SERIES,
    SOURCE,
    VALUE,
    EnergyColdStore,
)

_HUB = "HB_BUSAVG"
#: (nom de série, parseur, méthode transport, colonne de valeur) pour les prévisions.
_FORECASTS = [
    ("load_forecast", parse_load_forecast, "fetch_load_forecast", "forecast_load_mw"),
    ("available_capacity", parse_system_adequacy, "fetch_system_adequacy", "forecast_capacity_mw"),
    ("net_load_forecast", parse_net_load_forecast, "fetch_net_load_forecast", "net_load_mw"),
]


def extract_long(transport: ErcotTransport, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Extrait RTM + prévisions sur [start, end] en format long énergie (tz UTC préservé)."""
    frames: list[pd.DataFrame] = []

    # Série réalisée (RTM) : publish_time = interval_start (connu en fin d'intervalle).
    rtm = parse_rtm_spp(transport.fetch_rtm_spp(start, end, _HUB))
    frames.append(
        pd.DataFrame(
            {
                SOURCE: "ercot",
                SERIES: "rtm_spp",
                PUBLISH_TIME: rtm.index,
                INTERVAL_START: rtm.index,
                VALUE: rtm.to_numpy(dtype=float),
            }
        )
    )

    # Prévisions : publish_time issu du rapport (point-in-time).
    for series_name, parse_fn, fetch_name, value_col in _FORECASTS:
        raw = getattr(transport, fetch_name)(start, end)
        parsed = parse_fn(raw).reset_index(drop=True)
        frames.append(
            pd.DataFrame(
                {
                    SOURCE: "ercot",
                    SERIES: series_name,
                    PUBLISH_TIME: parsed["publish_time"],
                    INTERVAL_START: parsed["interval_start"],
                    VALUE: parsed[value_col].astype(float),
                }
            )
        )

    return pd.concat(frames, ignore_index=True)


def backfill(
    transport: ErcotTransport,
    store: EnergyColdStore,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    chunk_days: int = 7,
) -> int:
    """Backfille [start, end] par tranches dans ``store`` ; renvoie le nb de lignes neuves."""
    total = 0
    cursor = pd.Timestamp(start)
    stop = pd.Timestamp(end)
    step = pd.Timedelta(days=chunk_days)
    while cursor < stop:
        chunk_end = min(cursor + step, stop)
        total += store.write(extract_long(transport, cursor, chunk_end))
        cursor = chunk_end
    return total


def main() -> None:  # pragma: no cover (opérationnel, nécessite la clé + réseau)
    """Point d'entrée opérationnel. Régler la plage selon profondeur d'archive + quota."""
    transport = GridstatusIoTransport(limit=200_000)
    store = EnergyColdStore(Path("data/cold/ercot"))
    written = backfill(transport, store, "2024-06-01", "2024-10-01", chunk_days=7)
    print(f"{written} lignes écrites dans data/cold/ercot. Versionner : dvc add data/cold/ercot")


if __name__ == "__main__":  # pragma: no cover
    main()
