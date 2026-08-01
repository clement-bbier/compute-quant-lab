# P08 — Synthèse de la démo moteur

> `results/last_run.json` et `results/mlruns/` sont générés localement (gitignorés,
> cf. `results/.gitignore`) — ce document est l'artefact **committé** qui adosse les
> chiffres cités ailleurs (CLAUDE.md, README). Reproductible par construction (seed fixée) :
> relancer `uv run python projects/08_backtest_risk_engine/run_demo.py` régénère
> exactement les mêmes métriques.

## Run de référence (SIMULÉ)

- Stratégie : `ZScoreMeanReversion` (window=32, z_scale=2.0) sur fixture synthétique
  déterministe (`demo_fixtures.py`, seed=42, 512 observations).
- Coûts : frais 10 bps + slippage 5 bps (`LinearCostModel`).
- `n_trials = 1` (config figée *a priori*, pas de recherche d'hyperparamètres).

| Métrique | Valeur |
|---|---:|
| PnL total (capital=1) | 0.1150 |
| Sharpe (annualisé) | **0.6154** |
| Max drawdown | -0.0468 |
| Turnover | 93.686 |
| Hit ratio | 0.4746 |

**Lecture** : ce n'est **pas** une revendication d'alpha — P08 est le **moteur**, pas une
stratégie candidate. Le but de cette démo est de prouver que le pipeline (garde-fou
look-ahead + coûts + noyau Rust + tracking MLflow) tourne bout-en-bout et produit des
métriques reproductibles. Un Sharpe modeste (0.62) sur un mean-reversion z-score
synthétique n'est pas suspect (contrairement à un Sharpe très élevé, cf. P02 §backtest-pitfalls).

## Reproductibilité

Seed fixée (42), ordre de sommation fixe côté noyau Rust (`backtest_loop`), parité
bit-exacte avec l'oracle Python (`core/backtest/reference_loop.py`, testée). Run MLflow
loggué (params + métriques + SHA git + `dvc_version` — résout à `no-dvc-data` en
l'absence de données réelles versionnées, cf. CLAUDE.md racine).
