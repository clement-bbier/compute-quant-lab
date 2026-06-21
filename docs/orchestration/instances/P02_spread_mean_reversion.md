<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P02 — spread_mean_reversion

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`,
> les skills `/cointegration-analysis`, `/spread-trading-playbook`, `/backtest-pitfalls`.
> Livrable de session = un **plan d'implémentation**, pas du code.

## 0. Identité & cadre Git
- **ID** : P02 — couche Stratégie. **Branche** : `feature/P02-spread_mean_reversion`.
- **Worktree** : `git worktree add ../lab-P02 -b feature/P02-spread_mean_reversion integration`
- **Module possédé (écris UNIQUEMENT ici)** : `projects/02_spread_mean_reversion/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, **et tout `core/`** (lecture seule) → patch via convergence.

## 1. Thèse
Si la jambe énergie et la jambe compute sont cointégrées, le spark spread (pricé par
**P01**, `core.pricing.SparkSpreadPricer`) dévie temporairement de son équilibre de long
terme puis y revient. On parie sur ce retour à la moyenne. Edge : marchés déconnectés
(énergie liquide, compute fragmenté) → mispricings mean-reverting exploitables.

## 2. Flux de données vérifiés
Aucune nouvelle source : consomme la **série de spread** produite par `core.pricing`
(P01) sur l'historique aligné (énergie ENTSO-E réelle + compute Silicon Data/stub). Tout
en point-in-time, UTC.

## 3. Deux paliers
- **PoC-now** : (a) tester la cointégration énergie↔compute (Engle-Granger / Johansen, skill
  `/cointegration-analysis`) ; (b) construire un signal **z-score** d'entrée/sortie sur le
  spread ; (c) backtester via le moteur **P08** (`core.backtest.BacktestEngine`) → Sharpe,
  drawdown, turnover. Polyglotte autorisé si une jambe critique le justifie.
- **Institutional-target** : position sizing dynamique, demi-vie estimée, regime-switching,
  modèle d'exécution réaliste, Sharpe dégonflé (multiple testing).

## 4. Architecture (SOLID / DI)
`MeanReversionStrategy(z_entry, z_exit, lookback)` implémente le `Strategy` (Protocol) de
`core.backtest` : `signal(view: PointInTimeView) -> position`. La moyenne/écart-type du
spread à t n'utilisent QUE des données ≤ t (fenêtre glissante). La cointégration est
estimée hors du backtest mais point-in-time. Coûts injectés (`CostModel` de P08).

## 5. Code à faire grossir
- **Dans `projects/02_spread_mean_reversion/`** : `src/cointegration.py`, `src/strategy.py`,
  `src/run_backtest.py`, `notebooks/`, `results/`. Réutilise `core.pricing`, `core.backtest`.
- **Dans `core/`** : RIEN (lecture seule). Ce qui devient générique → patch convergence.

## 6. Tests-first
(a) cointégration sur 2 séries synthétiques **cointégrées connues** (et rejet d'un couple
non-cointégré) ; (b) signal z-score sur série à déviation contrôlée ; (c) **anti look-ahead**
(moyenne/sigma à t sur ≤ t) ; (d) backtest **déterministe** (seed). pytest.

## 7. Reproductibilité
MLflow via `core.backtest.tracking.tracked_run` (params z, lookback, coûts + SHA + DVC).
DVC pour les données. Tracer `n_trials` (combien de seuils z testés) — anti multiple-testing.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** (via `agent-architect` / `/new-agent`) : invoquer `backtest-runner`
  pour l'exécution et **`risk-validator`** (adversaire) avant de croire tout Sharbe > 2.
- **Références** : demi-vie OU, tests de cointégration robustes → `literature-scout`.
- **Skills/rules** : `/cointegration-analysis` + `/spread-trading-playbook` existent ; signaler tout manque.

## 9. Dépendances
- **Amont** : **P01** (pricing, dans `main`), **P08** (backtest, dans `main`).
- **Modules core requis** : `core.pricing`, `core.backtest` (lecture).
- **Externe** : `statsmodels` (cointégration), déjà dans les deps.

## 10. Risques & angles morts
Cointégration **spurieuse** ; look-ahead dans l'estimation de l'équilibre ; **overfitting**
des seuils z (multiple testing) ; backtest sur historique compute court (stub). Le
`risk-validator` doit pouvoir casser le résultat (skill `/backtest-pitfalls`).

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (cointégration, signal, anti look-ahead, déterminisme).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Backtest loggué MLflow (params + métriques + SHA + DVC).
- [ ] Synthèse `results/` : cointégration trouvée ?, Sharpe, DD, pièges couverts.
- [ ] Rien écrit hors `projects/02_…`. Commit sur la branche. Ni merge ni push.
