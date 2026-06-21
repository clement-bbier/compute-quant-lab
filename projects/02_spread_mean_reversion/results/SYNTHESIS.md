# P02 — Synthèse du backtest & verdict adversarial

> Run de référence : `last_run.json` (graine 42, 2000 obs horaires, **données SIMULÉES**).
> Cross-check exécution : `backtest-runner` (isolé). Audit adversarial : checklist `/backtest-pitfalls`.

## 1. Résultat (run SIMULÉ, `simulated=True`)

| Métrique | Valeur |
|---|---|
| PnL total | 4.068 |
| **Sharpe (annualisé √8760)** | **7.70** |
| Max drawdown | −20.6 % |
| Turnover | 90.0 |
| Hit ratio | 0.17 |
| n_trades | 90 |

Diagnostics cointégration (in-sample) : EG p ≈ 1.9e-08 (cointégré), Johansen n_relations = 2,
demi-vie ≈ 15.2 h, hedge ratio ≈ 0.0022. **Déterminisme confirmé** (métriques bit-pour-bit
identiques sur deux runs, `backtest-runner`).

## 2. Cointégration trouvée ?
Sur le jeu simulé, **oui** par construction (compute = coût énergie + OU stationnaire). Mais c'est
un **artefact** : Johansen voit un rang plein (2 relations sur 2 séries = les deux séries jugées
stationnaires) car le couplage à l'énergie est ténu (hedge ratio 0.0022) → le compute est dominé
par l'OU et *paraît* stationnaire. Ce n'est **pas** un système I(1) cointégré propre. À refaire sur
données réelles.

## 3. Verdict adversarial (`/backtest-pitfalls`) — le Sharpe est-il crédible ? **NON.**

| # | Piège | Sévérité | Géré par le code ? |
|---|---|---|---|
| 1 | **Look-ahead** | Faible | ✅ Garde-fou P08 `GuardedView` actif (test rouge `view.at(t+1)` → `LookAheadError`) ; z-score sur ≤ t. ⚠️ Le *diagnostic* de cointégration du run est full-sample (pas le signal) → gater via `rolling_cointegration`. |
| 2 | **Overfitting / multiple-testing** | Faible | ✅ `n_trials=1`, seuils z fixés a priori (non optimisés), tracé MLflow. ❌ Deflated Sharpe non appliqué (requis dès qu'on scanne). |
| 3 | **Walk-forward / OOS** | **Élevée** | ❌ Tout in-sample. Aucune découpe train/test, ni purged-embargo CV. |
| 4 | **Sharpe 7.70 non crédible** | **Élevée** | ❌ (a) données synthétiques où la stratégie épouse le processus OU (zéro risque de modèle) ; (b) annualisation horaire √8760 sur rendements **auto-corrélés** (mean-reversion) → Sharpe gonflé (≈ ÷5 en quotidien) ; (c) hit_ratio 0.17 + Sharpe 7.7 → PnL concentré sur peu de trades (distribution asymétrique, fragile au timing). |
| 5 | **Cointégration spurieuse** | Moyenne | ✅ Discipline correcte : p-value **MacKinnon** via `coint` (pas un ADF brut), testée pour *rejeter* deux marches indépendantes. ❌ Mais validée seulement in-sample. |
| 6 | **Coûts réalistes (compute illiquide)** | **Élevée** | ❌ 15 bps round-trip est optimiste : sur le compute fragmenté le **slippage domine** (cf. `/spread-trading-playbook`), le short de location GPU est difficile/impossible, capacité limitée. Modèle de coût linéaire symétrique irréaliste. |
| 7 | **Reproductibilité** | — | ✅ Seed + déterminisme bit-exact + MLflow (params/métriques/SHA/DVC) + `n_trials`. `dvc_version=no-dvc-data` (normal : aucune donnée réelle versionnée). |

**Drapeau le plus grave** : le résultat n'est **pas un alpha** — c'est une validation d'infrastructure
sur données simulées dont le générateur est connu. Le Sharpe élevé est *attendu* et trompeur.

## 4. Avant de croire à un quelconque alpha (actionnable)
1. **Données réelles** : énergie ENTSO-E (token en cours) + historique compute (Silicon Data payant
   ou accumulation des snapshots Vast.ai/RunPod).
2. **Cointégration point-in-time gating** : décider d'entrer en marché sur `rolling_cointegration`
   (≤ t), jamais sur le diagnostic full-sample.
3. **Walk-forward / OOS** avec purged k-fold + embargo (anti-fuite temporelle).
4. **Deflated Sharpe** dès qu'un seuil z est balayé (Bailey & López de Prado).
5. **Modèle d'exécution compute réaliste** : slippage dominant, asymétrie, contrainte de short/capacité.
6. **Fréquence d'annualisation honnête** (quotidien, ou de-annualiser) au lieu de √8760 sur des
   rendements auto-corrélés.

## 5. Note de gouvernance
L'agent `risk-validator` décrit dans le `CLAUDE.md` racine §6 **n'est pas enregistré** dans cet
environnement : cet audit a été conduit manuellement via la checklist `/backtest-pitfalls`. Créer
l'agent (via `agent-architect` / `/new-agent`) est un item de **croissance labo** → `CONVERGENCE.md`.
