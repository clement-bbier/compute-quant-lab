"""Collecteur de prix GPU — accumule l'historique compute jour après jour.

L'historique des prix de location GPU n'existe PAS rétroactivement : les marketplaces
n'exposent que le prix courant. On le construit donc en relevant (snapshot) régulièrement
le prix live et en l'horodatant. Planifier ce script via cron (ex. toutes les heures).

Sortie : un fichier horodaté append-only dans data/snapshots/, qui devient avec le temps
la série temporelle propriétaire du labo — un atout que personne d'autre n'a.

NOTE : la fonction d'appel marketplace est un STUB à brancher sur l'API réelle
(Vast.ai / RunPod) dans core/ingestion/gpu_market.py.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"


def fetch_live_gpu_prices() -> list[dict]:
    """STUB : remplacer par l'appel réel à l'API marketplace.

    Doit renvoyer une liste de dicts, p. ex. :
        [{"gpu_model": "H100", "price_eur_per_hour": 1.55, "availability": 120}, ...]
    """
    raise NotImplementedError(
        "Brancher sur core.ingestion.gpu_market (API Vast.ai / RunPod)."
    )


def snapshot() -> Path:
    """Relève le prix live et l'append dans un CSV horodaté (UTC)."""
    now = dt.datetime.now(dt.timezone.utc)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOT_DIR / f"gpu_prices_{now:%Y%m}.csv"

    rows = fetch_live_gpu_prices()
    write_header = not out.exists()
    with out.open("a", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["snapshotted_at", "gpu_model", "price_eur_per_hour", "availability"]
        )
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow({"snapshotted_at": now.isoformat(), **r})
    return out


if __name__ == "__main__":
    snapshot()
