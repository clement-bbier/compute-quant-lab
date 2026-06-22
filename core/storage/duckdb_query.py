"""Couche requête DuckDB (Phase 1) : SQL analytique embarqué sur le lac Parquet.

DuckDB lit le Parquet partitionné **directement en SQL**, en process, **zéro serveur** —
idéal pour l'EDA, les jointures point-in-time à l'échelle et la construction de features
(P07/P09). Coût quasi nul : on n'introduit pas de base à administrer tant que la donnée
reste batch (cf. roadmap §3 Phase 1, §4 anti-sur-ingénierie).

La requête s'exécute sur une vue ``prices`` exposant le schéma canonique (colonnes
:data:`~core.storage.schema.COLUMNS` + la partition ``month``). Le lac versionné DVC
étant immuable, une même requête rejouée sur la même version DVC est reproductible.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from core.storage.parquet_store import ParquetPriceStore

#: Schéma DuckDB de la vue vide (lac à froid) — aligné sur le cold store enrichi + partition.
_EMPTY_VIEW_SCHEMA = (
    "snapshotted_at TIMESTAMP WITH TIME ZONE, source VARCHAR, gpu_model VARCHAR, "
    "lease_type VARCHAR, price_usd_per_hour DOUBLE, availability BIGINT, "
    "region VARCHAR, gpu_memory_gb DOUBLE, vcpu BIGINT, ram_gb DOUBLE, disk_gb DOUBLE, "
    "provider_detail VARCHAR, month VARCHAR"
)


def query(sql: str, store: ParquetPriceStore, *, view: str = "prices") -> pd.DataFrame:
    """Exécute ``sql`` sur le lac Parquet de ``store``, exposé comme la vue ``view``.

    Parameters
    ----------
    sql
        Requête SQL DuckDB référençant la vue ``view`` (défaut ``prices``).
    store
        Le cold store dont la racine Parquet est interrogée.
    view
        Nom de la vue exposant le lac (défaut ``prices``).

    Returns
    -------
    pandas.DataFrame
        Le résultat de la requête. Sur un lac vide, la vue a le bon schéma mais 0 ligne
        (requêtes rejouables même à froid).
    """
    con = duckdb.connect()
    try:
        files = sorted(store.root.rglob("*.parquet"))
        if files:
            # CREATE VIEW n'accepte pas de paramètre préparé : le glob (chemin interne
            # contrôlé) est inliné en POSIX, simple quote échappée par sécurité.
            glob = (store.root / "**" / "*.parquet").as_posix().replace("'", "''")
            # union_by_name : le lac est hétérogène (parquet d'avant l'enrichissement du
            # schéma, sans les colonnes descriptives). Sans union par NOM, DuckDB lit par
            # position et lève « schema mismatch in glob » dès qu'on sélectionne une colonne
            # absente des vieux fichiers ; avec, les colonnes manquantes sont NULL-fillées.
            con.execute(
                f"CREATE VIEW {view} AS SELECT * FROM read_parquet("
                f"'{glob}', hive_partitioning => true, union_by_name => true)"
            )
        else:
            con.execute(f"CREATE TABLE {view} ({_EMPTY_VIEW_SCHEMA})")
        return con.execute(sql).fetchdf()
    finally:
        con.close()
