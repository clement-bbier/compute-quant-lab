"""Collecteur de prix GPU — accumule l'historique compute jour après jour.

L'historique des prix de location GPU n'existe PAS rétroactivement : les marketplaces
n'exposent que le prix courant. On le construit donc en relevant (snapshot) régulièrement
le prix live et en l'horodatant. Planifier ce script via cron (ex. toutes les heures).

Sortie : la série propriétaire append-only dans ``data/snapshots/`` (versionnée DVC),
un atout que personne d'autre n'a. L'écriture passe par
:class:`~core.ingestion.snapshot_store.CsvSnapshotStore`, donc le collecteur est
**idempotent** : le relancer ne crée jamais de doublon.

Le relevé live réel vient de :func:`core.ingestion.gpu_market.fetch_live_gpu_prices`
(Vast.ai aujourd'hui ; clés via ``.env``).
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.ingestion.gpu_market import fetch_live_gpu_prices
from core.ingestion.snapshot_store import CsvSnapshotStore

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"


def snapshot(store: CsvSnapshotStore | None = None) -> Path:
    """Relève le prix live de toutes les marketplaces configurées et l'append (dédupliqué).

    Parameters
    ----------
    store
        Store de destination. Par défaut : ``data/snapshots/`` du dépôt.

    Returns
    -------
    pathlib.Path
        Le fichier mensuel écrit (ou le répertoire si tout était déjà présent).
    """
    store = store or CsvSnapshotStore(SNAPSHOT_DIR)
    rows = fetch_live_gpu_prices()
    path = store.append(rows)
    logger.info("Snapshot collecté : %d relevés -> %s", len(rows), path)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    snapshot()
