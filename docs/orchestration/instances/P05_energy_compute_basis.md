<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P05 — energy_compute_basis

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`.
> Livrable de session = un **plan d'implémentation**, pas du code.

## 0. Identité & cadre Git
- **ID** : P05 — couche Stratégie. **Branche** : `feature/P05-energy_compute_basis`.
- **Worktree** : `git worktree add ../lab-P05 -b feature/P05-energy_compute_basis integration`
- **Module possédé (écris UNIQUEMENT ici)** : `projects/05_energy_compute_basis/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, tout `core/` (lecture seule).

## 1. Thèse
Le spark spread varie **par région** : prix élec régionaux (FR/DE, ENTSO-E) × **PUE** local
× efficience matérielle. Le **basis** entre régions ouvre un arbitrage géographique (placer la
charge GPU là où le spread est le plus large). P05 mesure et exploite ce basis.

## 2. Flux de données vérifiés
Consomme `core.pricing.SparkSpreadPricer` (**P01**) appliqué **par région** (énergie ENTSO-E
FR/DE réelle) et l'indice compute (**P04**). PUE/efficience par région = config injectée
(`core.utils.config`). Tout point-in-time, UTC.

## 3. Deux paliers
- **PoC-now** : (a) pricer le spark spread pour ≥ 2 régions ; (b) calculer le **basis** (différence
  ajustée PUE) point-in-time ; (c) identifier les dislocations et leur persistance.
- **Institutional-target** : optimisation de routing de charge, coûts/latence de transfert,
  contraintes de capacité, signal tradable inter-régions.

## 4. Architecture (SOLID / DI)
`BasisCalculator` pur : consomme un `SparkSpreadPricer` (P01) par région via DI ; `RegionConfig`
(PUE, FX, efficience) injecté. Pas de chemin en dur, pas d'I/O caché (rules).

## 5. Code à faire grossir
- **Dans `projects/05_energy_compute_basis/`** : `src/basis.py`, `src/region_config.py`,
  `src/run_basis.py`, `notebooks/`, `results/`.
- **Dans `core/`** : RIEN (lecture seule).

## 6. Tests-first
(a) basis sur **fixtures multi-région** à valeurs connues ; (b) **ajustement PUE** correct
(sensibilité documentée) ; (c) **anti look-ahead** ; (d) cohérence unités/fuseau (rule data-integrity).

## 7. Reproductibilité
MLflow (régions, PUE, FX, fenêtre + SHA + DVC) via `core.utils.tracking`. DVC pour les séries régionales.

## 8. CROISSANCE DU LABO (obligatoire)
- **Sources/MCP** : exploiter le MCP `energy-data` pour les prix régionaux ENTSO-E.
- **Nouveaux employés** : `risk-validator` avant de croire à un arbitrage géographique « gratuit ».
- **Références** : basis trading énergie, locational marginal pricing → `literature-scout`.

## 9. Dépendances
- **Amont** : **P01** (pricing), **P04** (indice compute) — tous deux dans `main`.
- **Modules core requis** : `core.pricing`, `core.ingestion`, `core.utils.config` (lecture).
- **Externe** : token ENTSO-E (multi-région) / MCP `energy-data`.

## 10. Risques & angles morts
**PUE régional = hypothèse forte** (peu observable) ; données compute par région limitées
(souvent un prix global) → le basis peut être surtout porté par l'énergie ; look-ahead ;
sur-interprétation d'un arbitrage non exécutable (coûts de transfert ignorés au PoC).

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (basis multi-région, ajustement PUE, anti look-ahead, unités).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Run MLflow loggué + données DVC.
- [ ] Synthèse `results/` : amplitude du basis, sensibilité PUE, limites d'exécution.
- [ ] Rien écrit hors `projects/05_…`. Commit sur la branche. Ni merge ni push.
