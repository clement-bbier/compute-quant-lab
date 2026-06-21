---
name: market-scan
description: Dispatche un essaim de subagents de veille en parallèle pour cartographier le marché émergent du compute, chacun sur une facette disjointe. À invoquer pour une session de collecte d'information massive.
---
# Market Scan — essaim de veille parallèle

But : rassembler un maximum d'information fiable sur le compute comme classe d'actifs,
en parallèle, sans redondance. Les agents collectent et synthétisent ; ils n'écrivent
jamais de code.

## Facettes (sous-questions DISJOINTES — une par agent)
Lancer un subagent `literature-scout` par facette, chacun avec un brief ciblé :

1. **Structure du marché GPU** : acteurs (Vast.ai, RunPod, hyperscalers), mécanismes de
   prix, liquidité, fragmentation, transparence.
2. **Marchés forward / futures du compute** : existe-t-il des contrats à terme, des places
   de marché, des indices ? Qui price le compute à terme ?
3. **Dynamique des prix de l'énergie** : drivers du spot élec EU, lien gaz/météo/renouvelable,
   spreads régionaux (Dunkerque, etc.).
4. **Classes d'actifs comparables** : comment d'autres « commodités numériques » ou
   l'électricité elle-même ont été financiarisées — analogies et limites.
5. **Littérature académique** : papers récents (arXiv, SSRN) sur le pricing du compute,
   l'arbitrage énergie/calcul, le spark spread numérique.
6. **Cadre réglementaire / risques** : ce qui pourrait contraindre un desk compute.

## Règles
- Chaque agent PARAPHRASE, ne copie aucun texte sous copyright, et cite ses sources.
- Chaque agent renvoie une synthèse hiérarchisée : « ce qui change quelque chose pour nous »
  en premier.
- Dédupliquer à la convergence : la session pilote fusionne les synthèses dans
  `references/` (un fichier par facette) et signale les contradictions entre agents.

## Cadence
Le market-scan est PONCTUEL (coûte des tokens). Le relancer quand le marché bouge,
pas en continu. Démarrer avec 4-6 facettes disjointes, pas plus.
