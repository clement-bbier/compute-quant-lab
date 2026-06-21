---
name: spread-trading-playbook
description: Méthodologie de construction d'une stratégie d'arbitrage de spread (ici énergie vs compute) une fois la cointégration établie. À invoquer pour passer du signal statistique à une stratégie tradable.
---
# Spread Trading Playbook

Présuppose une relation cointégrée validée (voir /cointegration-analysis).

## Construction de la stratégie
1. **Normaliser le spread** en z-score sur fenêtre glissante point-in-time.
2. **Règles d'entrée/sortie** : entrer quand |z| dépasse un seuil (ex. 2), sortir au retour
   vers 0. Le seuil est un hyperparamètre — à optimiser AVEC prudence (cf. backtest-pitfalls).
3. **Sizing** : position inversement proportionnelle à la volatilité du spread ; cap de risque.
4. **Coûts** : modéliser frais + slippage. Sur un actif illiquide comme le compute,
   le slippage domine — être conservateur.
5. **Stop / régime** : couper si la cointégration casse (le spread ne revient plus).

## Spécificité énergie↔compute
- La jambe énergie est liquide et a un historique profond (ENTSO-E).
- La jambe compute est illiquide, peu d'historique, exécution incertaine. Traiter
  le signal comme indicatif tant que la série compute collectée est courte ;
  commencer en paper-trading.

## Métriques de validation
PnL cumulé, Sharpe, max drawdown, turnover, hit ratio, sensibilité au coût.

## Référence
`references/stat-arb/` (Ernie Chan, *Algorithmic Trading*) ; `references/energy-markets/`.
