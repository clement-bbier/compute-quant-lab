<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# WD — compute_benchmark (indice public, data-product & portfolio)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/orchestration/money-parallel-plan.md`,
> `docs/storage-roadmap.md`, `docs/git-workflow.md`, `docs/parallel-ops.md`. Livrable = un **plan**.

## 0. Identité & cadre Git
- **ID** : WD — couche vitrine (data-product). **Branche** : `feature/WD-compute_benchmark`.
- **Worktree** : `git worktree add ../lab-WD -b feature/WD-compute_benchmark integration`
- **Module possédé (écris UNIQUEMENT ici)** : `projects/13_compute_benchmark/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, tout `core/` (lecture seule).
- **⚠️ Visibilité PUBLIQUE** : ceci est la **vitrine vendable** + portfolio. Publie un benchmark **utile** mais **pas l'edge de timing** (ça c'est WP / privé).

## 1. Thèse
Packager l'**indice spot compute multi-venues** comme un **benchmark public propre** :
le « prix de référence d'une GPU-heure », par modèle, avec la **dispersion inter-venues**.
C'est (a) un **data-product** (personne n'a d'historique compute propre et point-in-time)
et (b) une **pièce de portfolio** qui démontre tout le pipeline. Réutilise tout l'existant.

## 2. Flux de données vérifiés
Lit le **cold store** réel (`core.storage` Parquet — snapshots Vast/RunPod accumulés 24/7
via GitHub Actions, branche `data-snapshots`) et construit l'indice via
`core.ingestion.build_spot_index` (P04, distribution intra-venue déjà corrigée). Tout point-in-time, UTC.

## 3. Deux paliers
- **PoC-now** : (a) série d'**indice canonique** par modèle GPU (H100, B200…) sur l'historique réel
  accumulé ; (b) **stats de dispersion** (écart inter-venues, % d'écart, qui est moins cher) ;
  (c) **dashboard Streamlit de démo** (courbe d'indice + dispersion). Granularité publiable.
- **Institutional-target** : feed/API, historique profond, méthodo publiée (façon indice de marché).

## 4. Architecture (SOLID / DI)
Réutilise `core.storage.ParquetSnapshotStore` (lire le lac) + `core.ingestion.build_spot_index`
(agréger). Logique pure côté calcul ; I/O (lecture lac, dashboard) explicite et isolé. Aucune
réécriture de `core/` — que de la consommation.

## 5. Code à faire grossir
- **Dans `projects/13_compute_benchmark/`** : `src/index_series.py` (indice point-in-time sur le lac),
  `src/dispersion.py` (stats inter-venues), `dashboard/app.py` (Streamlit démo), `notebooks/`, `results/`.

## 6. Tests-first
(a) indice sur fixture (réutilise les conventions P04) ; (b) dispersion correcte (écart connu →
valeur attendue) ; (c) **anti look-ahead** (indice à t sur snapshots ≤ t) ; (d) robustesse données creuses (peu d'historique au début).

## 7. Reproductibilité
MLflow (params d'agrégation, fenêtre + SHA + version DVC) via `core.utils.tracking`. Lit la donnée versionnée.

## 8. CROISSANCE DU LABO (obligatoire)
- C'est l'actif **vendable** : documenter clairement la méthodo (auditeur externe doit comprendre l'indice).
- **Frontière edge** : ne publie PAS le signal « louer maintenant / sur X » (privé, WP). Ici = **mesure**, pas **décision**.
- Handoff convergence : `pyproject` testpaths `projects/13…/tests` ; éventuel `streamlit` déjà en dep.

## 9. Dépendances
- **Amont** : P04 (indice), P11 (storage), W1 (providers) — tous dans `main`. **Modules core** : `core.storage`, `core.ingestion` (lecture).

## 10. Risques & angles morts
Historique compute **court** au début (l'indice sera maigre — assumer, il grossit) ; **donner l'edge**
en publiant trop fin (garder la granularité « benchmark », pas « signal ») ; survivorship des venues.

## 11. Definition of Done (PoC-now)
- [ ] Indice multi-venues + dispersion sur l'historique réel ; dashboard démo qui tourne.
- [ ] Tests verts (indice, dispersion, anti look-ahead) ; `ruff` & `mypy core` verts.
- [ ] Run MLflow loggué ; synthèse `results/` (méthodo + état de l'historique).
- [ ] Rien écrit hors `projects/13_…`. Aucun edge de timing publié. Commit sur la branche. Ni merge ni push.
