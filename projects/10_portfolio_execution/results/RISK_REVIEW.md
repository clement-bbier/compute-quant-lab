# P10 — Revue adversariale (travail du risk-validator, fait inline)

> L'agent `risk-validator` n'existe pas encore dans `.claude/agents/` (zone protégée, à créer en
> convergence — CONVERGENCE.md §3). En attendant, on applique sa discipline ici : **attaquer le
> PnL net**, traquer look-ahead / overfitting / coûts sous-estimés (skill `/backtest-pitfalls`).

## Verdict
**Aucun alpha n'est revendiqué.** Le PoC valide une *mécanique de desk*, pas une stratégie. Le
PnL net (−0.54) est négatif et c'est le résultat **attendu et honnête** : les producteurs sont
des mocks sans edge. Publier ce chiffre comme performance serait une faute — il ne mesure que la
correction du pipeline.

## Checklist `/backtest-pitfalls`
1. **Look-ahead** — ✅ Neutralisé par construction : la décision à `t` passe par la `GuardedView`
   (≤ t) de P08 ; un producteur tricheur lève `LookAheadError` (`test_desk_lookahead`). La vol de
   pondération n'utilise que des rendements réalisés laggés.
2. **Overfitting / multiple testing** — ✅ Au PoC : `n_trials=1`, paramètres fixés *a priori*,
   aucune optimisation. ⚠️ Dès que de vrais signaux et un tuning entrent → deflated Sharpe obligatoire.
3. **Découpe temporelle** — ✅ Pas de shuffle (moteur séquentiel). N/A ici (rien n'est *fitté*) ;
   à réinstaurer (walk-forward, embargo) quand P09/ML alimentera le desk.
4. **Survivorship / univers** — ⚠️ Non couvert : une seule série synthétique. L'univers GPU réel
   change (hôtes qui entrent/sortent) → à traiter au branchement des vrais signaux.
5. **Coûts réalistes** — ✅ Cœur du projet : coûts linéaires + impact convexe, **PnL jugé au net**.
   La sensibilité montre que le turnover élevé (86.5) rend la stratégie fragile aux coûts.
6. **Stationnarité de régime** — ⚠️ Un seul régime simulé. Tester multi-régime avant toute conclusion.
7. **Reproductibilité** — ✅ Seed fixe, run MLflow (params + SHA + DVC), snapshot `last_run.json`.

## Angles morts spécifiques à l'agrégation (§10)
- **Corrélations ignorées** : l'inverse-vol pondère par vol marginale, pas par contribution au
  risque conjointe. Deux signaux fortement corrélés (ex. P06 et P09 sur le même facteur) seraient
  sur-alloués → faux sentiment de diversification. **Action** : `ERCScheme` (risk-parity) au
  palier institutionnel ; le seam existe déjà.
- **Sur-confiance composite** : agréger des signaux chacun overfitté produit un PnL net flatteur
  *in-sample*. **Action** : attaquer le net agrégé sur données out-of-sample, pas chaque signal isolé.
- **Coûts sous-estimés** : κ et bps sont des hypothèses. **Action** : calibrer sur exécutions
  réelles ; la capacité (impact dépendant du notionnel/liquidité) n'est pas encore modélisée.

## Ce qu'il faudrait pour croire un futur résultat positif
Vrais signaux (P02/P06/P09), out-of-sample multi-régime, coûts calibrés, deflated Sharpe, et une
pondération corrélation-aware. Tant que ces conditions ne sont pas réunies : **pipeline OK,
alpha = 0**.
