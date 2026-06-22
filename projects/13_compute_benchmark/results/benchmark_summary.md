# Compute Spot Benchmark — synthèse du run

Indice spot **réel** (provenance `real_spot`), point-in-time, UTC. Mesure publiée :
prix de référence GPU-heure (fix quotidien canonique 00:30 UTC) + dispersion
inter-venues descriptive. **Aucun signal de timing** (« louer sur X maintenant ») publié.

## État de l'historique (honnête — il est maigre au début, il grossit)
- Relevés : **250** · venues : **2** (runpod, vastai)
- Instants distincts : **4** · span : **5.7 h**
- Fenêtre : 2026-06-22 12:56:58.007071+00:00 → 2026-06-22 18:36:00.036491+00:00
- Fix quotidiens calculés sur la grille : **1**

## Agrégat
- Modèles publiés : **6** (B200, H100, H200, RTX4090, RTX5090, V100)
- Spread % inter-venues moyen (fix définis) : **64.06%**

## Dernier fix par modèle

| Modèle | Indice $/GPU·h | Venues | Spread % | Moins chère |
|---|---|---|---|---|
| B200 | 4.8785 | 2 | 41.47% | vastai |
| H100 | 2.5900 | 1 | n/a (mono-venue) | — |
| H200 | 1.9930 | 2 | 5.22% | vastai |
| RTX4090 | 0.2544 | 2 | 67.25% | vastai |
| RTX5090 | 0.5742 | 2 | 40.35% | vastai |
| V100 | 0.1148 | 2 | 166.01% | vastai |

## Niveaux moyens par venue (descriptif, fenêtre — PAS un signal de timing)

| Modèle | Venue | Niveau moyen $/h | Escompte moyen vs indice |
|---|---|---|---|
| B200 | runpod | 5.8900 | +20.73% |
| B200 | vastai | 3.8670 | -20.73% |
| H100 | runpod | 2.5900 | +0.00% |
| H200 | runpod | 2.0450 | +2.61% |
| H200 | vastai | 1.9410 | -2.61% |
| RTX4090 | runpod | 0.3400 | +33.62% |
| RTX4090 | vastai | 0.1689 | -33.62% |
| RTX5090 | runpod | 0.6900 | +20.17% |
| RTX5090 | vastai | 0.4583 | -20.17% |
| V100 | runpod | 0.2100 | +83.01% |
| V100 | vastai | 0.0195 | -83.01% |
