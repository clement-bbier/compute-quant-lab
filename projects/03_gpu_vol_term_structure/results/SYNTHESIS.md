# P03 — Synthèse vol & term structure

> Run de démonstration. Reproductible : `src/run_analysis.py` (MLflow). Chiffres bruts :
> [`run_summary.json`](run_summary.json). MLflow run `bfbeeba40674413a8a77d487c487ccf1`.

## 1. Couverture du run

| Élément | Valeur |
|---|---|
| GPU / fix | H100 |
| Jambe spot | spot **synthétique de démo** (seed fixe), 1.7765 $/GPU·h |
| Jambe forward | **SIMULÉE** (Schwartz 1-facteur, modèle `schwartz_mc_python`) |

**Note d'honnêteté** : l'historique compute est court (snapshots récents). Tant que la
série réelle est mince, le run tourne sur un spot synthétique étiqueté démo ; il bascule
sur l'indice réel dès que `data/snapshots/` est assez profond, sans autre changement.

## 2. Volatilité (annualisée)

| Estimateur | Vol |
|---|---|
| Réalisée (fenêtre 20) | **99.6 %** |
| EWMA (λ=0.94) | **97.4 %** |

## 3. Structure par terme (SIMULÉE) & signal

| Descripteur | Valeur |
|---|---|
| Forme | **contango** |
| Pente ($/GPU·h/j) | 0.0002221 |
| Courbure (butterfly) | -0.1143 |
| Signal directionnel | **-1** (contango : carry négatif (roll-yield)) |

> ⚠️ **Frontière réel/simulé** : la term structure et le signal dérivent d'une courbe
> forward **simulée** (`simulated=True`). Conditionnels au modèle, jamais
> servis comme un prix de marché observé.

## 4. Limites

- Historique compute court → vol et calibration peu robustes (intervalle large).
- Forward simulée → la forme de la courbe reflète le modèle (mean-reversion Schwartz),
  pas une anticipation de marché observée.
- Signal roll-yield = convention (backwardation→long) : à valider sur données réelles
  une fois les futures compute listés / la série spot accumulée.
