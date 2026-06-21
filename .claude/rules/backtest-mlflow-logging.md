---
paths:
  - "core/backtest/**"
  - "projects/**"
---
# Reproductibilité des backtests

- Tout backtest DOIT logger un run MLflow contenant : params, métriques, **SHA git**
  et **version DVC** des données. Utiliser `core.backtest.tracking.tracked_run`
  (qui compose `core.utils.tracking.run`).
- Aucune métrique de stratégie n'est publiée sans run MLflow rejouable (`run_id`).
- Tracer le nombre d'essais (`n_trials`) pour le multiple testing (deflated Sharpe
  au palier institutionnel). S'articule avec `backtest-runner` (exécution) et
  `risk-validator` (adversaire).
