---
name: run-backtest
description: Procédure standard pour exécuter et logger un backtest de stratégie d'arbitrage compute/énergie de façon reproductible. À invoquer dès qu'on veut évaluer une stratégie ou un signal.
---
# Run Backtest

Protocole reproductible. Suivre les étapes dans l'ordre, sans en sauter.

1. **Figer le contexte** : récupérer le SHA git courant et la version DVC des données
   (`dvc status`). Refuser de lancer si l'arbre git est sale (`git status` non vide).
2. **Charger les données** via `core.ingestion` (jamais de chemin en dur). Vérifier
   qu'elles sont passées par `core.data_quality` (sinon, lancer d'abord /data-quality-check).
3. **Découpe temporelle** : train/val/test chronologiques, pas de shuffle.
4. **Exécuter** le moteur `core.backtest` avec seed fixée.
5. **Métriques obligatoires** : PnL cumulé, ratio de Sharpe, max drawdown, turnover,
   hit ratio. Coûts (frais + slippage) modélisés.
6. **Logger dans MLflow** : params, métriques, SHA git, version DVC, figure du PnL.
   Stocker les artefacts dans `projects/NN/results/`.
7. **Sanity check** : si Sharpe > 2 sur des données réelles, signaler un risque
   d'overfitting/look-ahead et déléguer une revue au subagent `risk-validator`.
