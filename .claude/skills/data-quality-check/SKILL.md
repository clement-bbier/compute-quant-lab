---
name: data-quality-check
description: Pipeline de validation qualité d'une série temporelle (énergie ou prix GPU) avant utilisation. À invoquer après toute ingestion et avant tout backtest.
---
# Data Quality Check

Sur la série ciblée dans `data/interim/` :

1. **Schéma** : colonnes attendues, types, index temporel UTC trié et unique.
2. **Trous** : détecter les gaps vs la fréquence attendue ; documenter la méthode de
   comblement (forward-fill borné, interpolation, ou drop) — jamais de comblement silencieux.
3. **Outliers** : flag des valeurs hors plage physique (prix élec négatifs = possibles ;
   prix GPU négatifs = impossibles). Loguer, ne pas supprimer en aveugle.
4. **Point-in-time** : vérifier qu'aucune révision rétroactive n'a écrasé l'historique.
5. **Rapport** : produire un court résumé (n lignes, % gaps, n outliers) et n'écrire la
   série validée dans `data/processed/` que si les checks passent.
