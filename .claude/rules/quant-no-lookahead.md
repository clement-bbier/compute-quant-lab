---
paths:
  - "core/backtest/**"
  - "projects/**"
---
# Rigueur quantitative (anti-biais)

- INTERDIT : utiliser à l'instant t une information non disponible à t (look-ahead).
  Les features sont calculées uniquement sur des données passées (point-in-time).
- Modéliser explicitement les coûts (frais, slippage) dans tout backtest.
- Séparer strictement train / validation / test temporellement (pas de shuffle aléatoire
  sur des séries temporelles).
- Tout résultat de backtest doit être reproductible : seed fixée, version DVC des données
  loggée, params loggés dans MLflow.
- Méfiance envers un Sharpe trop beau : suspecter overfitting / data snooping avant de célébrer.
