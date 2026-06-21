# P11 — storage_layer · handoffs convergence

> Ce lot écrit **uniquement** dans `core/storage/` + `infra/collectors/` (+ l'artefact
> `data/snapshots/`). Tout ce qui touche la **zone protégée** (`pyproject.toml`, `.claude/`)
> ou le module **P04 `core/ingestion/`** est listé ici pour la session de convergence — il
> n'est **pas** appliqué dans ce worktree.

## 1. Dépendances & config (`pyproject.toml`)
- Ajouter aux `dependencies` : **`duckdb>=1.0`**, **`pyarrow>=15`** (le cold store et la
  couche requête en dépendent). `pyarrow` était déjà tiré transitivement par `pandas` ;
  `duckdb` a été installé **ad hoc** dans le venv du worktree (`pip install duckdb`) — à
  officialiser dans le lockfile (`uv add duckdb pyarrow`).
- Inclure les tests du module dans la CI : ajouter **`core/storage/tests`** aux `testpaths`
  (ou au matrix de la CI qui lance chaque dossier en isolation, cf. note `pyproject` §pytest).
- **Stub pré-existant (P04)** : `mypy` 1.20 signale `core/ingestion/gpu_market.py` (`import
  requests`, `[import-untyped]`, non silencé par `ignore_missing_imports`). Ajouter
  **`types-requests`** aux deps `dev` (installé ad hoc ici pour un `mypy core` vert). Non lié à P11.

## 2. Fix distribution (P04 — `core/ingestion/`)  ⚠️ ne PAS éditer ici
- **Constat** : `parse_vastai_offers` émet **une ligne par offre** (N prix H100 distincts au
  même instant). La clé de dédup de `CsvSnapshotStore` `(t, source, modèle, bail)` les **écrase
  à une seule ligne** → la distribution intra-source est détruite *dans le store*, alors que
  l'agrégation appartient à l'indice (standard Silicon Data).
- **Apporté par P11** : `ParquetPriceStore` déduplique au **contenu complet de ligne** (prix +
  dispo inclus) → **conserve la distribution** des offres, reste un journal d'observations fidèle.
- **À faire en convergence** : adapter `build_spot_index` / `MarketplaceProxySource` pour
  **agréger la distribution intra-source** en un `VenueRate` (trimmed-mean par source) **avant**
  le `latest_by_source`. Aujourd'hui, sur des offres au même timestamp, `latest_by_source`
  retiendrait **une offre arbitraire** (dernier itéré) — incorrect dès que le store préserve la
  distribution. Le store fournit désormais la matière première ; l'indice doit faire l'agrégation.

## 3. Repointer l'indice sur le cold store Parquet (P04)  ⚠️ ne PAS éditer ici
- `MarketplaceProxySource.fetch` lit aujourd'hui `CsvSnapshotStore.load()`. Le brancher sur le
  cold store Parquet : soit `ParquetPriceStore(...).read(as_of=...)`, soit une requête DuckDB
  (`core.storage.duckdb_query.query`) pour les jointures point-in-time à l'échelle.
- Bénéfice : lecture typée/colonne, point-in-time natif (`as_of`), versionnée DVC.

## 4. Seed réel + DVC-track du cold store  ⛔ bloqué dans ce worktree
- **Décision directeur** : *seed réel via collecteur live*. **Non exécutable ici** : ce worktree
  n'a **pas de `.env`** (créé via `git worktree add`, qui n'honore pas `.worktreeinclude`) et
  aucune clé `VASTAI_API_KEY` / `RUNPOD_API_KEY` dans l'environnement ; la lecture du `.env`
  principal est (correctement) refusée par le garde-fou crédentiels. Aucune donnée n'a été
  fabriquée (rule réel/simulé).
- **À exécuter dans un environnement avec tokens** (convergence ou poste avec `.env`) :
  ```bash
  # 1) relevé live -> double écriture CSV (P04) + Parquet (cold store)
  python -m infra.collectors.gpu_price_snapshot
  # 2) versionner le lac Parquet produit (pointeurs *.parquet.dvc, cf. .gitignore)
  dvc add data/snapshots/**/*.parquet      # ou : dvc add data/snapshots
  git add data/snapshots/**/*.dvc data/.gitignore
  # 3) run consommateur (logge la version DVC via MLflow) — repro
  python -m core.storage.demo
  ```
- La couche est prête : dès qu'une donnée existe, `ParquetPriceStore` la partitionne et DuckDB
  la requête ; `core.utils.tracking` logge la version DVC.

## 5. Nouvel employé — persona `infra-engineer` (à enregistrer via `agent-architect` / `/new-agent`)
> Décrit ici (la zone `.claude/agents/` est protégée). À matérialiser en convergence.

- **name** : `infra-engineer`
- **description** : « Services planifiés, stockage et CI du labo : collecteurs (snapshot prix
  GPU), cold store Parquet/DVC, couche requête DuckDB, et — phases institutionnelles —
  docker-compose Redpanda/TimescaleDB/Redis. À appeler pour poser/maintenir l'infra données. »
- **tools** : `Read, Write, Edit, Bash` (build/test/dvc/compose) — pas de réseau applicatif.
- **système (esquisse)** : possède `core/storage/` + `infra/` ; respecte 1 worktree = 1 module ;
  ne touche jamais la zone protégée (remonte un patch convergence) ; tests-first ; cold store
  immuable et versionné DVC ; **local-first** (docker-compose), managed cloud au seul palier
  institutionnel ; ne monte Redpanda/Timescale/Redis **qu'après** décision de ticker intraday
  (anti-sur-ingénierie, roadmap §4).

## 6. Skill / rule candidate
- **Rule** (path-scopée modèles/entraînement) : « l'entraînement lit **toujours** le cold store
  versionné (`core.storage`), **jamais** le hot store (Timescale/Redis) ». Matérialise le principe
  non négociable de `docs/storage-roadmap.md` §0. À ajouter sous `.claude/rules/` en convergence.
