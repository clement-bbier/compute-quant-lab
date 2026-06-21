# Synthèse P06 — Base théorique des futures compute

> ⚠️ **THÉORIQUE/SIMULÉ.** Futures compute (settlement SDH100RT) **non listés**.
> Forwards issues d'un modèle (cost-of-carry / Schwartz P04), jamais d'un marché
> observé. Données chiffrées : [`futures_pricing_summary.json`](futures_pricing_summary.json).

## Hypothèses du run de démo
- Spot : `2.50 $/GPU·h` — **source `assumed_fallback`** (aucun snapshot réel accumulé ;
  repli loggué). Brancher l'indice spot réel (P04) dès que la série est disponible.
- Taux de financement `r = 4 %/an` ; convenience yield exogène `y = 1 %/an` (hypothèse).
- Forward Schwartz P04 : `κ=0.05/j, θ=2.5, σ=0.3` (paramètres d'hypothèse).

## Term structure de la base `F − S` ($/GPU·h)

| Échéance | Base carry (r,y exo.) | Base forward P04 | Yield implicite P04 (annualisé) |
|---:|---:|---:|---:|
| 30 j  | +0.0062 | +1.334 | −5.17 |
| 90 j  | +0.0185 | +1.421 | −1.79 |
| 180 j | +0.0372 | +1.421 | −0.87 |
| 360 j | +0.0750 | +1.421 | −0.42 |

- **Carry exogène** : report léger et croissant (`r > y` ⇒ contango modéré).
- **Forward P04** : base bien plus haute — la mean-reversion Schwartz (θ + prime de
  variance) pousse la forward au-dessus du spot ; traduit en termes de carry, cela
  donne un **convenience yield implicite fortement négatif** (le portage « coûte »
  davantage que le seul financement). Les deux modèles se rejoignent exactement via ce
  yield implicite (cohérence testée).

## Sensibilités (carry, à 360 j)
`∂F/∂r = F·τ`, `∂F/∂y = −F·τ`, `∂F/∂τ = F·(r−y)` — analytiques, testées. Ex. `∂F/∂τ ≈ 0.077`.

## Lecture desk
Le jour du listing, la base observée se compare à cette base théorique : un écart
révèle le convenience yield réellement price par le marché. Tant que les futures ne
sont pas listés, **ces chiffres sont un cadre de valorisation, pas un signal tradable**.
