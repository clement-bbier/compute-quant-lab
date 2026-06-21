# P09 — Synthèse & verdict adversarial

> Rôle tenu : **risk-validator** (adversaire). L'agent dédié n'existe pas encore dans
> l'environnement (cf. [CONVERGENCE.md](../CONVERGENCE.md) §3) — l'audit `/backtest-pitfalls`
> a donc été conduit à la main, en cherchant activement les failles, pas en les excusant.

## Run de référence (SIMULÉ)

- `run_id` : voir `results/last_run.json` (MLflow sous `results/mlruns/`).
- Données : `synthetic_spark_spread_gas_lead`, **`simulated=True`** — spark spread pricé par
  P01, mené par un lead exogène (gaz) **faible** connu avec lag de publication (P07).
- Modèle : ensemble de 3 XGBoost (graines 11/22/33), validation purged k-fold (5) + embargo 5,
  horizon 1, bande neutre 0.05. `n_trials = 1` (hyperparamètres figés *a priori*).

| Métrique | Valeur | Lecture |
|---|---:|---|
| Sharpe (annualisé) | **0.17** | Quasi nul. |
| Deflated / Probabilistic Sharpe (PSR) | **0.66** | Probabilité modeste que le vrai SR > 0. |
| Max drawdown | **-0.88** | Repli profond → stratégie fragile. |
| Turnover | **1050** (903 trades) | Très élevé : les coûts mangent le signal. |
| Hit ratio | **0.24** | Faible. |
| PnL total (capital=1) | 0.43 | Positif mais volatil. |

**Verdict : aucun alpha revendiqué.** Le résultat est volontairement *peu spectaculaire* —
et c'est le point : la rigueur de validation **n'a pas fabriqué** de faux alpha. À comparer au
Sharpe 7.70 non crédible de P02 (la stratégie y épousait le processus générateur).

## Checklist `/backtest-pitfalls` — point par point

1. **Look-ahead bias** — *couvert.* Trois défenses empilées et **testées** : features ≤ t
   (invariance par troncature du futur, `test_lookahead`/`test_pipeline`), purge de l'horizon
   du label + embargo (`test_validation`), lecture du seul `proba[view.t]` à l'exécution
   (`test_strategy`). Pas de normalisation globale dans les features (XGBoost = splits, invariant
   d'échelle) → pas de fuite par scaling. Le `gas_std` global du synthétique est dans le **DGP**,
   jamais une feature.
2. **Overfitting / sélection** — *maîtrisé au PoC.* `n_trials = 1`, aucune recherche
   d'hyperparamètres ; l'ensemble de graines réduit la variance, ce n'est pas de la sélection.
   ⚠️ Toute future grille (profondeur, seuils, fenêtres) **doit** incrémenter `n_trials` → le PSR
   chutera mécaniquement (`expected_max_sharpe` croît avec les essais).
3. **Découpe temporelle** — *correcte.* Purged k-fold + embargo, **jamais de shuffle** ;
   un splitter qui fuit ferait virer `test_purge_removes_label_horizon_overlap` au rouge.
4. **Survivorship / univers** — *N/A au PoC* (série unique synthétique). Sur réel, l'univers GPU
   entre/sort : danger à traiter au câblage des marketplaces.
5. **Coûts réalistes** — *modélisés* (10 bps frais + 5 bps slippage, moteur P08). Ils **dominent**
   ici (turnover 1050) : c'est précisément ce qui tue l'edge faible. Honnête.
6. **Stationnarité de régime** — *non testée* : un seul régime synthétique, drawdown -0.88 =
   signal de fragilité. Le réel a des ruptures de régime → limite assumée.
7. **Reproductibilité** — *garantie.* Graine fixée, run **déterministe** (métriques identiques à
   la ré-exécution), MLflow loggue params + `n_trials` + SHA git + version DVC + figure PnL.

## Ce qu'il faudrait pour y croire (palier institutionnel)

- Données **réelles** (ENTSO-E + historique compute profond) — le synthétique ne prouve que le
  *pipeline*.
- **Réduire le turnover** : l'arbitrage bande neutre / coûts est réel (une bande plus large
  ↓ turnover ; cf. paramètre `neutral_band`) → sizing conscient des coûts, voire pénalité de
  turnover.
- **Deflated Sharpe avec vrai `n_trials`** dès qu'on tune, **walk-forward** (et non k-fold), test
  multi-régimes, LSTM/TFT + stacking.
- Faire **casser** chaque résultat par l'agent `risk-validator` une fois créé.
