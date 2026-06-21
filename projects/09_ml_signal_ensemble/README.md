# P09 — ML Signal Ensemble (direction du spark spread)

Ensemble ML directionnel sur le **digital spark spread**, backtestable **sans glue** via
l'interface `Strategy` du moteur P08. La discipline centrale est l'**anti-overfitting** :
validation temporelle stricte (purged CV + embargo), Sharpe dégonflé, `n_trials` loggé.

## Pipeline

```
core.features (P07, ≤t)  ┐
spread P01 (lags/roll ≤t) ├─►  X  ──►  PurgedKFold + embargo  ──►  proba OOS  ─┐
label = sign(Δspread_{t+h})┘            (ensemble XGBoost, oos_predict)         │
                                                                                ▼
                          PrecomputedSignalStrategy.signal(view) = pos(proba[view.t])
                                                                                │
                                       moteur de backtest P08 (GuardedView) → PnL/Sharpe
```

**Trois défenses anti-look-ahead empilées** : (a) features point-in-time (réutilise le garde-fou
P07), (b) purge + embargo dans la CV (la prédiction de `t` n'a jamais vu son futur), (c)
`GuardedView` du moteur à l'exécution (hérité de P08, gratuit).

## Lancer

```bash
# 1. Noyau Rust du moteur P08 (prérequis du backtest réel — comme P05)
uv run maturin develop -m core/backtest/_loop/Cargo.toml --release

# 2. Tests de la couche modèle (logique pure ; exige le noyau Rust pour importer core.backtest)
uv run pytest core/models/tests -q

# 3. Run headline (entraînement + backtest + MLflow, sur SIMULÉ)
uv run python projects/09_ml_signal_ensemble/src/run_train.py

# 4. Tests projet (smoke + provenance ; skippés sans noyau Rust)
uv run pytest projects/09_ml_signal_ensemble/tests -q
```

Le run logge un run MLflow sous `results/mlruns/` (params + `n_trials` + SHA git + version DVC +
figure PnL) et écrit `results/last_run.json`. Tableau de bord : `mlflow ui`.

## Briques réutilisables promues dans `core/models/`

| Module | Rôle |
|---|---|
| `protocols` | Contrats `Model` / `Splitter` (DI). |
| `validation` | `PurgedKFold`, `oos_predict`, `deflated_sharpe_ratio`, `expected_max_sharpe`. |
| `pipeline` | `FeaturePipeline` (consomme `core.features`), `build_labels`, `SpreadFeatureSpec`. |
| `xgboost_model` | `XGBoostDirectionModel` (déterministe), `SeedBaggingEnsemble`. |
| `strategy` | `PrecomputedSignalStrategy` (adaptateur vers `core.backtest`). |

## État & honnêteté
PoC sur **données simulées étiquetées** (`provenance.simulated=True`). Résultat **modeste et
non vendu comme alpha** : le verdict adversarial complet (checklist `/backtest-pitfalls`) vit dans
[results/SYNTHESIS.md](results/SYNTHESIS.md). Le palier institutionnel (réel, walk-forward, LSTM/TFT,
deflated Sharpe avec vrai `n_trials`) est listé dans [CONVERGENCE.md](CONVERGENCE.md).
