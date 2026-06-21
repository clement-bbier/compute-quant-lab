# Roster des projets — usine de recherche du labo

> Carte des 10 projets de recherche. Chaque projet = une instance focalisée =
> une branche `feature/PNN-<nom>` = un worktree = un module possédé disjoint.
> Source de vérité de l'**ordre de dépendance** et de la **propriété des modules**.
> La propriété fine vit aussi dans [parallel-ops.md](../parallel-ops.md) ; ce roster
> la spécialise au niveau projet.

## Principe de couches

```
  Couche FONDATION (racines, aucune dépendance amont) : P01 · P04 · P08
        │            │            │
        ▼            ▼            ▼
  Couche STRATÉGIE / RECHERCHE (dépend des racines)  : P02 P03 P05 P06 P07 P09
        │
        ▼
  Couche DESK (agrège les signaux)                   : P10
```

Les trois racines **P01 / P04 / P08** sont générées et lancées **en premier**, en
parallèle, car leurs modules possédés sont **disjoints** (`core/pricing/`,
`core/ingestion/`, `core/backtest/`) — zéro collision de merge.

## Grounding commun (à respecter dans tout plan)

- **Jambe énergie** : ENTSO-E / PJM, prix spot réels, historique profond, fiable.
- **Jambe compute (spot)** : indice **Silicon Data réel** (accès payant disponible).
- **Jambe compute (forward)** : futures compute CME **annoncés mais NON listés**
  (revue réglementaire) → **courbe forward SIMULÉE**, jamais présentée comme réelle.
- **Point-in-time** strict (anti look-ahead), tout I/O par `core/`, tout backtest loggué MLflow + SHA git + version DVC.
- **Polyglotte dès le PoC** : Python par défaut ; Rust/C#/C++ sur les jambes critiques (latence/perf) quand justifié.

## Table des projets

| ID | Nom court | Thèse (1 ligne) | Module possédé | Dépend de | Couche |
|---|---|---|---|---|---|
| **P01** | `digital_spark_spread` | Pricer le spread compute−énergie (revenu GPU − coût élec). | `core/pricing/` + `projects/01_digital_spark_spread/` | — | Fondation |
| **P04** | `compute_index_curve` | Construire l'indice spot compute (Silicon Data) + courbe forward simulée. | `core/ingestion/` (jambe compute) + `infra/collectors/` + `projects/04_compute_index_curve/` | — | Fondation |
| **P08** | `backtest_risk_engine` | Moteur de backtest reproductible + métriques de risque, garde-fous anti look-ahead. | `core/backtest/` + `projects/08_backtest_risk_engine/` | — | Fondation |
| **P02** | `spread_mean_reversion` | Cointégration énergie↔compute → stratégie de mean-reversion du spread. | `projects/02_spread_mean_reversion/` (+ features dédiées) | P01, P08 | Stratégie |
| **P03** | `gpu_vol_term_structure` | Modéliser la vol des prix GPU et la structure par terme du forward simulé. | `projects/03_gpu_vol_term_structure/` | P04 | Stratégie |
| **P05** | `energy_compute_basis` | Basis régional énergie↔compute ajusté PUE (FR/DE vs hubs compute). | `projects/05_energy_compute_basis/` | P01, P04 | Stratégie |
| **P06** | `compute_futures_pricing` | Pricer les futures compute (non listés) : carry, convenience yield, base spot/forward. | `core/pricing/` (dérivés) + `projects/06_compute_futures_pricing/` | P04 | Stratégie |
| **P07** | `exogenous_macro_signal` | Météo, gaz, buildout datacenter comme drivers exogènes du spread. | `core/features/` + `projects/07_exogenous_macro_signal/` | P01 | Stratégie |
| **P09** | `ml_signal_ensemble` | Ensemble ML (XGBoost / LSTM / TFT) prévoyant la direction du spread. | `core/models/` + `projects/09_ml_signal_ensemble/` | P01, P07, P08 | Stratégie |
| **P10** | `portfolio_execution` | Construction de portefeuille + simulation d'exécution/coûts, qualité desk. | `projects/10_portfolio_execution/` | P02, P06, P09, P08 | Desk |

> ⚠️ Conflit potentiel `core/pricing/` entre **P01** (spark spread) et **P06** (dérivés) :
> P06 ne démarre qu'après merge de P01, et travaille dans un sous-paquet dédié
> (`core/pricing/derivatives/`) pour rester disjoint. Idem `core/features/` : P02 et P07
> écrivent dans des sous-modules nommés par projet.

## Ordre de génération des prompts

1. **Vague 1 (racines, parallèle)** : P01, P04, P08.
2. **Vague 2** : P02, P03, P05, P06, P07 (après merge des racines dont elles dépendent).
3. **Vague 3** : P09, puis P10 (agrégation desk).
