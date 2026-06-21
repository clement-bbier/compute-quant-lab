<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P11 — storage_layer (Phase 0–1 de la roadmap stockage)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, **`docs/storage-roadmap.md`**, `docs/git-workflow.md`,
> `docs/parallel-ops.md`. Livrable = un **plan d'implémentation**, pas du code.

## 0. Identité & cadre Git
- **ID** : P11 — track infra/données. **Branche** : `feature/P11-storage_layer`.
- **Worktree** : `git worktree add ../lab-P11 -b feature/P11-storage_layer integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`core/storage/`** (nouveau) + `infra/collectors/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, et **`core/ingestion/`** (P04 : `snapshot_store.py`, `compute_index.py`) → tout besoin = patch convergence.

## 1. Thèse
Poser le **cold store reproductible** du labo : un historique compute/énergie **immuable,
point-in-time, versionné**, sur lequel tous les modèles s'entraînent à l'identique.
Implémente **Phase 0 (Parquet+DVC) + Phase 1 (DuckDB) + la couche d'abstraction** de
`docs/storage-roadmap.md`. Pas de temps réel ici (Phases 2–4 = institutionnel, documentées).

## 2. Flux de données vérifiés
Consomme les snapshots **réels** déjà collectés (`data/snapshots/*.csv`, Vast.ai + RunPod
live). Aucune nouvelle source externe. Sortie : un cold store Parquet versionné DVC + une couche requête.

## 3. Deux paliers
- **PoC-now** : (a) `core/storage/` avec **Protocols** (`PriceStore`, et stubs `TickStream`/`HotCache`
  documentés pour plus tard) ; (b) `ParquetPriceStore` (lecture/écriture Parquet partitionné
  source/mois, typé, append-only, idempotent) ; (c) **migration** `data/snapshots/*.csv → Parquet`
  + **DVC-track** ; (d) **DuckDB reader** (SQL embarqué sur le Parquet) ; (e) rewire du collecteur
  `infra/collectors/gpu_price_snapshot.py` pour écrire via `ParquetPriceStore`.
- **Institutional-target** : Redpanda (tick stream), TimescaleDB (hot historique), Redis (serving) — **documenté, pas codé** (cf. roadmap §3 Phases 2–4).

## 4. Architecture (SOLID / DI)
`PriceStore` (Protocol) : `write(frame)`, `read(query | as_of)` → impl `ParquetPriceStore`
(et plus tard `TimescalePriceStore`, sans toucher les consommateurs : OCP). DuckDB comme
moteur de requête sur le lac Parquet. Fonctions pures là où possible ; I/O explicite (rules).

## 5. Code à faire grossir
- **Dans `core/storage/`** : `__init__.py`, `protocols.py`, `parquet_store.py`, `duckdb_query.py`, `migrate.py`.
- **Dans `infra/collectors/`** : rewire du collecteur vers `ParquetPriceStore`.
- **Polyglotte** : non requis (I/O + SQL). Parquet/DuckDB sont déjà colonne/vectorisés.

## 6. Tests-first
(a) round-trip write→read Parquet (types, partition) ; (b) **idempotence** (ré-append = pas de
doublon) ; (c) **point-in-time** : `read(as_of=t)` ne renvoie que `snapshotted_at ≤ t` ;
(d) requête DuckDB sur fixture Parquet → résultat attendu ; (e) migration CSV→Parquet préserve
les lignes. pytest, fixtures déterministes (pas de réseau).

## 7. Reproductibilité
**Cœur du projet** : DVC-track le cold store ; un run consommateur logge la **version DVC**
(via `core.utils.tracking`, déjà câblé). DuckDB lit le Parquet versionné → requêtes rejouables.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** : fabriquer **`infra-engineer`** dispatchable via `agent-architect`/`/new-agent` (persona décrit, non enregistré).
- **Handoffs convergence** (touchent `core/ingestion/` de P04 — NE PAS éditer ici, lister) :
  (1) **fix distribution** : `CsvSnapshotStore` réduit N offres/modèle à 1 ligne → garder la
  distribution (l'agrégation appartient à l'indice P04) ; (2) pointer `compute_index.py` sur le
  Parquet ; (3) `pyproject.toml` : ajouter `duckdb`, `pyarrow` aux deps + testpaths `core/storage/tests`.
- **Skills/rules** : candidat rule « l'entraînement lit le cold store versionné, jamais le hot store ».

## 9. Dépendances
- **Amont** : aucune (consomme des données déjà présentes). **Externe** : `pyarrow`, `duckdb` (à déclarer → convergence), `dvc` (présent).

## 10. Risques & angles morts
Casser le format attendu par l'indice P04 (→ coordination convergence) ; perte de point-in-time
à la migration ; gonflement du Parquet sans partition ; confondre cold (repro) et hot (serving).

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (round-trip, idempotence, point-in-time, DuckDB, migration).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] `data/snapshots/` en Parquet **DVC-tracké** ; collecteur écrit via `ParquetPriceStore`.
- [ ] Synthèse `results/` + handoffs convergence listés (fix distribution, deps, index).
- [ ] Rien écrit hors `core/storage/` + `infra/collectors/`. Commit sur la branche. Ni merge ni push.
