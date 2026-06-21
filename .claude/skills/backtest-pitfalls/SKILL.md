---
name: backtest-pitfalls
description: Checklist anti-illusion pour tout backtest de ML financier (overfitting, p-hacking, biais de sélection). À invoquer systématiquement avant de croire un résultat. Cœur du travail du risk-validator.
---
# Backtest Pitfalls (ML financier)

Un backtest qui brille est coupable jusqu'à preuve du contraire. Distillé de la pratique
du ML financier (López de Prado et al.).

## Checklist
1. **Look-ahead bias** : aucune feature ne doit utiliser d'information future. Vérifier
   chaque feature ligne à ligne.
2. **Overfitting / sélection de modèle** : combien de configurations ont été essayées ?
   Plus on teste, plus un bon Sharpe arrive par hasard (multiple testing). Documenter le
   nombre d'essais ; ajuster (deflated Sharpe ratio).
3. **Découpe temporelle** : pas de shuffle aléatoire sur des séries. Utiliser une CV
   adaptée au temporel (purged k-fold, embargo) pour éviter la fuite entre train et test.
4. **Survivorship / sélection d'univers** : l'univers GPU change (hôtes qui entrent/sortent).
   Ne pas conditionner rétroactivement sur ce qui a survécu.
5. **Coûts réalistes** : un alpha qui meurt après frais+slippage n'est pas un alpha.
6. **Stationnarité du régime** : un modèle entraîné sur un régime de prix peut échouer
   au régime suivant. Tester sur plusieurs régimes.
7. **Reproductibilité** : seed fixée, version DVC des données, params MLflow. Si tu ne
   peux pas le reproduire, tu ne peux pas le croire.

## Verdict
Si un point échoue → le résultat n'est pas publiable. Le rôle du risk-validator est de
chercher activement ces failles, pas de les excuser.

## Référence
`references/ml-finance-pitfalls/` (López de Prado, *Advances in Financial Machine Learning*).
