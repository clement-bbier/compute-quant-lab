# Bibliographie — le canon du labo

> Méthodologie distillée + pointeurs vers les ouvrages. On ne copie aucun texte sous
> copyright : on encode des protocoles actionnables (voir les skills) et on cite les sources.

## Statistical arbitrage & cointégration
- Engle, R. & Granger, C. (1987), *Co-integration and Error Correction* — le test fondateur.
- Johansen, S. — test de cointégration multivarié (préféré pour ≥ 2 séries).
- Avellaneda, M. & Lee, J. (2010), *Statistical Arbitrage in the U.S. Equities Market*.
- Chan, E., *Algorithmic Trading: Winning Strategies and Their Rationale* — mise en pratique.
→ Méthodo distillée : `.claude/skills/cointegration-analysis`, `spread-trading-playbook`.

## Pièges du ML financier (CRITIQUE pour risk-validator)
- López de Prado, M., *Advances in Financial Machine Learning* — overfitting de backtest,
  purged k-fold, deflated Sharpe, meta-labeling.
→ Méthodo distillée : `.claude/skills/backtest-pitfalls`.

## Marchés de l'énergie & dérivés
- Eydeland, A. & Wolyniec, K., *Energy and Power Risk Management*.
- Clewlow, L. & Strickland, C., *Energy Derivatives: Pricing and Risk Management*.
- Le concept de *spark spread* (gaz→électricité) vient de cette littérature ; on l'adapte
  ici en *digital spark spread* (électricité→compute).
→ Notes : `references/energy-markets/`.

## Séries temporelles & prévision
- Hyndman, R. & Athanasopoulos, G., *Forecasting: Principles and Practice* (libre en ligne).
- Modèles : XGBoost (baseline), LSTM / Temporal Fusion Transformer (séquentiel).

## Sources de données de référence (connecteurs)
- ENTSO-E Transparency Platform — prix spot élec EU (officiel, gratuit, historique profond).
- S&P Global / Kensho — donnée financière institutionnelle (MCP connecté).
- Tavily — recherche web structurée pour la veille (MCP connecté).
