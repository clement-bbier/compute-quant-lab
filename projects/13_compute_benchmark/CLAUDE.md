# Projet 13 — Compute Spot Benchmark (indice public, data-product)

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo détaillée
> et état : [README.md](README.md). Couche **vitrine** (data-product + portfolio).

## Thèse spécifique
Packager l'**indice spot compute multi-venues** comme un **benchmark public propre** : le
« prix de référence d'une GPU-heure » par modèle, avec la **dispersion inter-venues**.
Personne n'a d'historique compute propre et point-in-time → c'est à la fois un data-product
et une pièce de portfolio qui démontre le pipeline de bout en bout. Réutilise tout l'existant.

## Modules possédés
- `projects/13_compute_benchmark/` **uniquement**.
- Lecture seule (consommation, jamais réécriture) : `core.storage`, `core.ingestion`, `core.utils`.
- Zone protégée intouchée (`CLAUDE.md` racine, `.claude/`, `.mcp.json`, `pyproject.toml`, `core/`).

## Architecture (SOLID / DI)
- **Lecture lac** : `core.storage.ParquetSnapshotStore` (cold store Parquet versionné).
- **Agrégation canonique** : `core.ingestion.build_spot_index` (P04, distribution intra-venue déjà corrigée).
- **Couche pure (ici)** : `src/benchmark/` — `index_series` (série point-in-time), `dispersion`
  (stats inter-venues + niveaux nommés), `report` (assemblage + état honnête de l'historique).
- **I/O isolé** : `run_build_benchmark.py` (MLflow + `results/`), `dashboard/app.py` (Streamlit).

## Frontière edge (vitrine PUBLIQUE — non négociable)
- On publie la **MESURE** : prix de référence (fix **quotidien** canonique 00:30 UTC) +
  dispersion descriptive (spread, %, CV) + niveau **moyen** par venue nommée sur la fenêtre.
- On ne publie PAS la **DÉCISION** : aucun signal de timing live « louer sur X maintenant »
  (edge privé → WP). La granularité reste « benchmark », pas « signal ».

## Réel / point-in-time
Spot **réel** (provenance `real_spot`, jamais simulé). Tout UTC tz-aware. Anti look-ahead
hérité de `build_spot_index` (aucune obs `> as_of`) ; un fix sans venue fraîche est **sauté**,
jamais comblé par carry-forward. Historique court au début (assumé) — il grossit.

## État d'avancement (PoC-now)
- [x] `index_series` : série d'indice point-in-time (grille quotidienne + cadence démo), tests verts
- [x] `dispersion` : spread/%/CV + niveaux nommés ; invariant anti-dérive vs `build_spot_index`
- [x] `report` : assemblage multi-modèles + `HistoryState` honnête
- [x] `run_build_benchmark.py` : run MLflow réel (`real_spot`) + `results/benchmark_summary.md`
- [x] `dashboard/app.py` : démo Streamlit (indice + dispersion + niveaux)
- [ ] Convergence : `pyproject` testpaths `projects/13…/tests` (zone protégée, hors périmètre WD)

## Lancement
```bash
uv run pytest -q projects/13_compute_benchmark/tests
uv run python projects/13_compute_benchmark/run_build_benchmark.py   # lit data/snapshots
uv run streamlit run projects/13_compute_benchmark/dashboard/app.py
```
