# Projet 09 — ML Signal Ensemble

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo détaillée
> et état : [README.md](README.md). Patches zone protégée : [CONVERGENCE.md](CONVERGENCE.md).

## Thèse spécifique
Prévoir la **direction du spark spread** (P01) par un **ensemble ML** nourri de features
exogènes point-in-time (P07) et de features dérivées du spread. Le signal est évalué par le
moteur de backtest P08. En finance + ML, **l'ennemi n°1 est l'overfitting** : la rigueur de
validation temporelle prime sur la complexité du modèle.

## Modules possédés
- **`core/models/`** (brique réutilisable) **+** `projects/09_ml_signal_ensemble/`.
- Lecture seule : `core.pricing` (P01), `core.features` (P07), `core.backtest` (P08).
- Interdit : tout le reste de `core/`, zone protégée racine (`CLAUDE.md`, `.claude/`, `.mcp.json`,
  `pyproject.toml`) → patches [CONVERGENCE.md](CONVERGENCE.md).

## Architecture (SOLID / DI) — `core/models/`
- `protocols.py` — `Model` (`fit`/`predict_proba`), `Splitter` : contrats injectables (DI).
- `validation.py` — `PurgedKFold` (purge horizon + embargo, **jamais de shuffle**), `oos_predict`
  (vecteur OOS aligné), `deflated_sharpe_ratio` (anti multiple-testing).
- `pipeline.py` — `FeaturePipeline` (consomme `core.features` P07 + features causales du spread),
  `build_labels` (signe du forward return).
- `xgboost_model.py` — `XGBoostDirectionModel` (déterministe), `SeedBaggingEnsemble`.
- `strategy.py` — `PrecomputedSignalStrategy` : adaptateur vers le `Strategy` Protocol de P08
  (lit `proba[view.t]`, mappe en position via une bande neutre).

## Insight clé (pont ML → backtest)
P08 ne passe au `Strategy` qu'une vue point-in-time sur la **série de prix**, pas la matrice de
features. On précalcule donc un vecteur de **probabilités OOS** (purged-CV) aligné sur l'index,
et l'adaptateur ne fait que le lire à `view.t`. Le modèle ne voit jamais les prix au runtime →
toute fuite est neutralisée *en amont*, et le garde-fou `GuardedView` reste gratuit (OCP).

## Frontière réel/simulé (non négociable)
`synthetic.DataProvenance.simulated` est **obligatoire** (sans défaut, rule `forward-real-simulated`) ;
un test échoue s'il manque. Au PoC, tout tourne sur du **simulé étiqueté** (pas bloqué par ENTSO-E).

## État d'avancement (PoC-now)
- [x] `core/models/` : protocols, purged-CV + embargo + OOS, deflated Sharpe, pipeline PIT, XGBoost
  déterministe + ensemble de graines, adaptateur `Strategy` — 30 tests verts.
- [x] Anti look-ahead (3 défenses), split temporel sans fuite, déterminisme, sanity bruit-pur.
- [x] Run headline simulé → backtest P08 → MLflow (params + n_trials + SHA + DVC + figure PnL).
- [x] Verdict adversarial `/backtest-pitfalls` ([results/SYNTHESIS.md](results/SYNTHESIS.md)).
- [x] `ruff` / `mypy core` / `pytest` verts.
- [ ] **Données réelles** (ENTSO-E + historique compute) ; **walk-forward** ; LSTM/TFT (palier 3b).
- [ ] Agent `risk-validator` (zone protégée → convergence, cf. CONVERGENCE.md).

## Résultats clés
Pipeline validé bout-en-bout sur **SIMULÉ**. Sharpe ~0.17, deflated/PSR ~0.66, drawdown profond,
turnover élevé : l'edge synthétique faible **ne survit pas aux coûts**. **Aucun alpha revendiqué** —
voir le verdict dans [results/SYNTHESIS.md](results/SYNTHESIS.md).
