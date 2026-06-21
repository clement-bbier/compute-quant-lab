# P11 — storage_layer · synthèse

**Branche** : `feature/P11-storage_layer` (base `integration`). **Périmètre** : Phase 0+1 de
`docs/storage-roadmap.md` — cold store reproductible, couche d'abstraction, requête DuckDB.
**Hors périmètre** : temps réel (Phases 2–4, documentées, non codées).

## Ce qui est livré (`core/storage/`)
- **`protocols.py`** — `PriceStore` (Protocol DI/SOLID) + stubs documentés `TickStream`
  (Redpanda, Phase 2) / `HotCache` (Redis, Phase 4). L'abstraction est posée *avant* tout
  backend → migration entre phases indolore (OCP).
- **`schema.py`** — schéma canonique du lac + `normalize_frame` (UTC tz-aware **obligatoire**,
  prix `float64`, dispo `int64`). Un horodatage naïf est **rejeté** (intégrité point-in-time).
- **`parquet_store.py`** — `ParquetPriceStore` : lac Parquet **partitionné `source` / mois**,
  append-only, **idempotent au contenu de ligne** (préserve la distribution des offres),
  `read(as_of=t)` **point-in-time** (anti look-ahead).
- **`duckdb_query.py`** — `query(sql, store)` : SQL embarqué (zéro serveur) sur le lac, vue
  `prices` ; gère le lac vide (schéma sans ligne).
- **`migrate.py`** — `migrate_csv_snapshots` : bascule CSV (P04) → Parquet, sans perte, idempotente.
- **`converters.py`** — `snapshots_to_frame` : unique point de couplage *lecture* avec `core.ingestion`.
- **`demo.py`** — run consommateur : EDA DuckDB + **log de la version DVC** (`core.utils.tracking`) → repro.
- **`infra/collectors/gpu_price_snapshot.py`** — rewire **double écriture** : CSV (P04, inchangé)
  + Parquet (cold store). Idempotent ; `fetch` injectable (tests sans réseau).

## Tests — `pytest core/storage/tests` : **23 passés**
| Famille | Fichier | Garantie |
|---|---|---|
| (a) round-trip | `test_parquet_roundtrip.py` | types, partition source/mois, **distribution préservée**, conformité `PriceStore`, rejet naïf |
| (b) idempotence | `test_idempotence.py` | ré-append = no-op ; offres distinctes conservées |
| (c) point-in-time | `test_point_in_time.py` | `read(as_of=t)` ⊆ `{snapshotted_at ≤ t}`, filtre source, rejet `as_of` naïf |
| (d) DuckDB | `test_duckdb_query.py` | SQL sur lac (agrégats), lac vide |
| (e) migration | `test_migrate.py` | CSV→Parquet préserve les lignes, idempotente |
| rewire | `test_collector_rewire.py` | double écriture, idempotence Parquet |
| run conso | `test_demo.py` | stats DuckDB (pure, sans MLflow) |

Méthode **TDD strict** : chaque comportement a vu son test échouer avant implémentation.
Fixtures déterministes, **zéro réseau**.

## Gate de sortie
- [x] `ruff check .` — All checks passed.
- [x] `mypy core` — propre (le crash initial était un cache `.mypy_cache` obsolète, purgé).
- [x] `pytest core/storage/tests` — 23 passés.
- [x] Synthèse + handoffs convergence (`CONVERGENCE.md`).
- [ ] **`data/snapshots/` en Parquet DVC-tracké — ⛔ bloqué** : seed *live* impossible ici
  (pas de `.env` dans le worktree, pas de token `VASTAI/RUNPOD`, lecture du `.env` principal
  refusée par le garde-fou crédentiels). **Aucune donnée fabriquée**. La couche est prête ;
  procédure exacte de seed + `dvc add` dans `CONVERGENCE.md` §4 (à exécuter avec tokens).
- [x] Rien écrit hors `core/storage/` + `infra/collectors/` (+ artefact `data/snapshots/`).
  Ni merge ni push.

## Note environnement
`duckdb 1.5.4` installé **ad hoc** dans le venv (déclaration formelle `pyproject` → convergence,
`CONVERGENCE.md` §1). `mlflow` absent de cet interpréteur → le run MLflow complet de `demo.main`
s'exécute dans l'env `uv` du labo ; `run_summary.json` ci-joint reflète un lac **vide** (0 ligne),
honnête avant seed.
