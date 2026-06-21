<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P03 — gpu_vol_term_structure

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`.
> Livrable de session = un **plan d'implémentation**, pas du code.

## 0. Identité & cadre Git
- **ID** : P03 — couche Stratégie. **Branche** : `feature/P03-gpu_vol_term_structure`.
- **Worktree** : `git worktree add ../lab-P03 -b feature/P03-gpu_vol_term_structure integration`
- **Module possédé (écris UNIQUEMENT ici)** : `projects/03_gpu_vol_term_structure/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, tout `core/` (lecture seule).

## 1. Thèse
La **volatilité** des prix GPU est un actif en soi, et la **structure par terme** de la
courbe forward (contango/backwardation) porte de l'information directionnelle. P03 modélise
la vol réalisée de l'indice spot compute (**P04**) et analyse la term structure de la
forward simulée (**P04**).

## 2. Flux de données vérifiés
Consomme l'**indice spot compute** (`core.ingestion.build_spot_index`, P04, réel via
snapshots) et la **courbe forward SIMULÉE** (`projects/04…/src/forward`, Schwartz 1-facteur).
⚠️ La forward est **simulée** (futures CME non listés) : tout résultat est conditionnel au modèle.

## 3. Deux paliers
- **PoC-now** : (a) vol réalisée de l'indice spot (réalisée glissante, **EWMA**, option GARCH) ;
  (b) analyse de la term structure de la forward (pente, courbure, contango vs backwardation) ;
  (c) signal directionnel simple dérivé de la pente.
- **Institutional-target** : surface de vol, modèle de vol stochastique, options sur futures.

## 4. Architecture (SOLID / DI)
`VolEstimator` (Protocol) : `estimate(returns) -> vol_series` → impls `RealizedVol`, `EwmaVol`,
`GarchVol` injectables. `TermStructureAnalyzer` pur : pente/courbure point-in-time. Pas d'I/O
caché côté analyse (rule python-quality).

## 5. Code à faire grossir
- **Dans `projects/03_gpu_vol_term_structure/`** : `src/vol.py`, `src/term_structure.py`,
  `src/run_analysis.py`, `notebooks/`, `results/`.
- **Dans `core/`** : RIEN (lecture seule). Promotion d'un estimateur générique → convergence.

## 6. Tests-first
(a) vol sur série à **vol analytique connue** (EWMA, réalisée) ; (b) term structure sur courbe
synthétique **contango** puis **backwardation** (signe de pente attendu) ; (c) **anti look-ahead**
(vol/pente à t sur ≤ t). pytest, fixtures déterministes.

## 7. Reproductibilité
MLflow (params estimateur, fenêtre, λ EWMA + SHA + DVC) via `core.utils.tracking`. Seed fixe.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** : aucun requis a priori ; `literature-scout` pour la modélisation de vol.
- **Références** : EWMA/GARCH sur commodités, term structure de l'énergie (analogie) → `references/`.
- **Skills/rules** : la rule `forward-real-simulated` s'applique (toute sortie dérivée de la forward = simulée).

## 9. Dépendances
- **Amont** : **P04** (indice spot + forward, dans `main`).
- **Modules core requis** : `core.ingestion` (lecture) ; la forward vit dans `projects/04` (lecture).
- **Externe** : `arch` (GARCH) si retenu — sinon EWMA pur numpy (préférer, éviter une dép neuve sans convergence).

## 10. Risques & angles morts
Historique compute **court** (snapshots récents) → vol peu robuste ; **forward simulée** (pas
réelle) → ne jamais présenter la term structure comme observée ; look-ahead dans la vol.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (vol, term structure contango/backwardation, anti look-ahead).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Run MLflow loggué + données DVC.
- [ ] Synthèse `results/` : régime de vol, forme de la term structure, limites (forward simulée).
- [ ] Rien écrit hors `projects/03_…`. Commit sur la branche. Ni merge ni push.
