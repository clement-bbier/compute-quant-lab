<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P09 — ml_signal_ensemble

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`,
> les skills `/backtest-pitfalls`, `/run-backtest`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : P09 — couche Stratégie (ML). **Branche** : `feature/P09-ml_signal_ensemble`.
- **Worktree** : `git worktree add ../lab-P09 -b feature/P09-ml_signal_ensemble integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`core/models/`** + `projects/09_ml_signal_ensemble/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, le reste de `core/` (lecture seule).

## 1. Thèse
Prévoir la **direction du spark spread** par un **ensemble ML** (baseline XGBoost ; LSTM/TFT
au palier supérieur), nourri par les features exogènes de **P07** (`core/features`) et la série
de spread de **P01**. Le signal est ensuite évalué par le moteur de backtest **P08**. En finance
+ ML, **l'ennemi n°1 est l'overfitting** : la rigueur de validation prime sur la complexité du modèle.

## 2. Flux de données vérifiés
Features : `core.features` (P07, point-in-time, lag de publication). Cible : direction du spread
(`core.pricing`, P01). Données réelles dès tokens présents, sinon **fixtures synthétiques
déterministes** (le réel est branché, le run tourne en simulé étiqueté en attendant). UTC, point-in-time.

## 3. Deux paliers
- **PoC-now** : baseline **XGBoost** sur features point-in-time ; **validation temporelle stricte**
  (purged k-fold + embargo, **jamais de shuffle**) ; signal → backtest P08 → Sharpe/DD ; **Sharpe
  dégonflé** (deflated, tenir compte du nombre d'essais).
- **Institutional-target** : LSTM/TFT, ensembling, inférence online (servie depuis le hot store), feature store.

## 4. Architecture (SOLID / DI)
`core/models/` : `Model` (Protocol) `fit/predict` → `XGBoostModel` ; `TemporalSplit`
(purged/embargo) ; `FeaturePipeline` consommant `core.features`. Le modèle produit un **signal**
conforme au `Strategy` de `core.backtest` (P08) → backtestable sans glue. DI partout, seed loggée.

## 5. Code à faire grossir
- **Dans `core/models/`** : `protocols.py`, `xgboost_model.py`, `validation.py` (purged CV), `__init__.py`.
- **Dans `projects/09_ml_signal_ensemble/`** : `src/run_train.py` (MLflow), `notebooks/`, `results/`.

## 6. Tests-first
(a) **anti look-ahead** : la matrice de features à t n'utilise que ≤ t (réutiliser le garde-fou P07) ;
(b) **split temporel** : purged/embargo, aucun chevauchement train/test (test rouge si fuite) ;
(c) **déterminisme** : seed → mêmes prédictions ; (d) métriques sur cible synthétique connue. pytest.

## 7. Reproductibilité
MLflow via `core.utils.tracking` (hyperparams, seed, **n_trials**, features, fenêtres + SHA + DVC).
Tracer le nombre d'essais → deflated Sharpe (anti multiple-testing). Données versionnées DVC.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** : `quant-researcher` (modélisation) ; **`risk-validator`** adversaire **obligatoire** avant de croire un Sharpe.
- **Références** : López de Prado (purged CV, deflated Sharpe, backtest overfitting), feature importance robuste → `literature-scout`.
- **Convergence** : `pyproject.toml` testpaths `core/models/tests` ; promotion d'estimateurs P03/P07 dans `core/features`.

## 9. Dépendances
- **Amont** : **P01** (spread), **P07** (features), **P08** (backtest) — tous dans `main`.
- **Modules core requis** : `core.pricing`, `core.features`, `core.backtest` (lecture). **Externe** : `xgboost` (déjà déclaré).

## 10. Risques & angles morts
**Overfitting / data snooping** (risque maximal) ; look-ahead dans le feature engineering ;
historique compute **court** → modèle fragile ; multiple testing ; fuite via normalisation globale.
Le `risk-validator` doit casser chaque résultat (skill `/backtest-pitfalls`). **Un Sharpe trop beau = suspect.**

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (anti look-ahead, split temporel sans fuite, déterminisme).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Entraînement + backtest loggués MLflow (params + n_trials + métriques + SHA + DVC).
- [ ] Synthèse `results/` : performance HONNÊTE (deflated), pièges couverts, limites.
- [ ] Rien écrit hors `core/models/` + `projects/09_…`. Commit sur la branche. Ni merge ni push.
