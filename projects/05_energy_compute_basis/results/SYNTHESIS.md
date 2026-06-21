# P05 — Synthèse du basis énergie ↔ compute

- Régions : FR, DE (référence = DE)
- Fenêtre : 2025-01-01 00:00:00+00:00 → 2025-01-31 23:00:00+00:00 (UTC)
- Sources : énergie = **synthetic**, compute = **synthetic** (compute GLOBAL)
- PUE régional (hypothèse) : FR=1.2, DE=1.45

## Amplitude & persistance du basis

| basis | moyenne (€/GPU·h) | écart-type | amplitude p95 | % temps disloqué | épisodes | demi-vie (h) |
|---|---|---|---|---|---|---|
| FR−DE | 0.01683 | 0.01632 | 0.04287 | 16.8% | 108 | 0.23 |

## Sensibilité PUE

Le basis est, à FX et prix compute égaux, porté par `power_kw·(pue_r·energy_r − pue_ref·energy_ref)/1000` : ↑ PUE d'une région ⇒ ↑ son coût ⇒ ↓ son spread ⇒ ↓ son basis. La sensibilité est testée (`test_pue_sensitivity_is_monotone`).

## Limites d'exécution (PoC)

- **PUE régional** = hypothèse forte, peu observable ; principal levier du basis ici.
- **Compute global** (une seule courbe) : le revenu s'annule entre régions → le basis est essentiellement un *basis énergie × PUE*, pas un vrai spread compute régional.
- **Coûts/latence de transfert ignorés** : ne pas conclure à un arbitrage exécutable.
- Suite institutionnelle : routing optimisé, contraintes de capacité, signal tradable.
