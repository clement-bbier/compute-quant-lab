# P03 — GPU Volatility & Term Structure

Couche **Stratégie** du labo : traiter la **volatilité** des prix GPU comme un actif et
exploiter la **structure par terme** de la courbe forward (contango/backwardation) comme
signal directionnel. Consomme les produits fondateurs de **P04** (indice spot + forward).

## Sources de données

| Jambe | Réel / Simulé | Source | Unité | Statut |
|---|---|---|---|---|
| Indice spot | **Réel** | `core.ingestion.build_spot_index` sur snapshots accumulés | $/GPU·h | branché (token-gated) |
| Courbe forward | **SIMULÉE** | P04 — Schwartz 1-facteur seedé sur le spot | $/GPU·h / échéance | branché (repli MC Python) |

> ⚠️ **Frontière réel/simulé** : la term structure et le signal dérivent d'une forward
> `simulated=True`. `TermStructure.simulated` est un champ **obligatoire** (sans défaut) ;
> un test échoue s'il est absent. Jamais servi comme un prix de marché observé.

## Méthodologie

### Volatilité (numpy pur, causale)
- **Réalisée** : écart-type glissant des log-returns sur fenêtre trailing (warmup → NaN).
- **EWMA** (RiskMetrics) : `σ²_t = λ·σ²_{t-1} + (1-λ)·r²_t`, réactive, λ par défaut 0.94.
- Annualisation par `periods_per_year` nommé (compute tradé 24/7 → 365).
- **Anti look-ahead** : `vol[t]` ne dépend que des returns d'indice ≤ t (testé par
  invariance à la troncature). GARCH = point d'extension du `VolEstimator` (Protocol).

### Structure par terme (pure)
- **Pente** : régression linéaire prix ~ échéance (`np.polyfit` degré 1).
- **Courbure** : butterfly `F_court − 2·F_milieu + F_long`.
- **Forme** : contango (pente > seuil), backwardation (pente < −seuil), sinon plat.

### Signal directionnel (convention roll-yield)
Commodités non stockables (analogie élec) : **backwardation → long (+1)**, **contango →
short (−1)**, bande neutre → **0**. Hérite du drapeau `simulated` de la term structure.

## Plage, profondeur & limites (état PoC)
- **Historique compute court** : la série propriétaire démarre à la première collecte ;
  tant qu'elle est mince, `run_analysis.py` tourne sur un spot **synthétique étiqueté démo**
  (seed fixe) et bascule sur l'indice réel dès `data/snapshots/` assez profond.
- **Forward simulée** : la forme de la courbe reflète le **modèle** (mean-reversion
  Schwartz), pas une anticipation de marché observée. Tout résultat est conditionnel.

## Lancer

```bash
uv sync --extra dev
# Analyse complète (vol + term structure + signal) + run MLflow + results/ :
uv run python projects/03_gpu_vol_term_structure/src/run_analysis.py
# Tests (testpaths racine n'inclut pas encore P03 -> chemin explicite) :
uv run pytest projects/03_gpu_vol_term_structure
```

## Reproductibilité

- **MLflow** : `run_analysis.py` logue params (fenêtre vol, λ EWMA, `periods_per_year`,
  modèle de courbe, `forward_simulated`) + métriques (vol réalisée/EWMA, pente, courbure,
  signal) + SHA git via `core.utils.tracking` (`experiments/mlruns`, `mlflow ui`).
- **Seed** fixe partout. MLflow 2026 → `MLFLOW_ALLOW_FILE_STORE=true` (géré par `tracking`).

## Handoff convergence
Voir [CONVERGENCE.md](CONVERGENCE.md) : ajout de P03 à `testpaths`, promotion éventuelle des
estimateurs de vol vers `core/`.
