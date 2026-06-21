# P05 — Energy ↔ Compute Basis

Mesure le **basis** du spark spread entre régions (FR/DE) : différence point-in-time des
spreads régionaux, chaque spread ajusté par le **PUE** local. Objectif PoC : quantifier
l'amplitude du basis, sa sensibilité au PUE, ses dislocations et leur persistance — et exposer
honnêtement pourquoi ce n'est pas (encore) un arbitrage exécutable.

## Idée

À FX et prix compute égaux entre régions, le revenu compute s'annule et

```
basis[r] = spread[r] − spread[ref] = power_kw·(pue_ref·energy_ref − pue_r·energy_r) / 1000
```

Le basis est donc, au PoC, un **spread de prix d'électricité pondéré par le PUE**. C'est
volontaire et assumé : le prix du compute n'a pas (encore) de granularité régionale.

## Architecture (SOLID / DI)

| Fichier | Rôle |
|---|---|
| `src/region_config.py` | `RegionConfig` (PUE, TDP, n_gpus, FX) + `build_regional_pricer` → un `SparkSpreadPricer` (P01) **par région** |
| `src/basis.py` | `BasisCalculator` **pur** (jointure interne point-in-time) + `detect_dislocations` (seuil + demi-vie AR(1)) |
| `src/data.py` | I/O : énergie ENTSO-E FR/DE (repli synthétique étiqueté) + indice compute P04 (repli étiqueté) |
| `src/run_basis.py` | Orchestration → run MLflow → `results/SYNTHESIS.md` |

Réutilise en lecture seule : `core.pricing` (P01), `core.ingestion` (P04),
`core.utils.config` / `core.utils.tracking`. Aucune écriture hors `projects/05_…`.

## Méthodologie

- **Point-in-time** : le pricer aligne le compute sur la grille énergie par as-of arrière ;
  le basis aligne les spreads régionaux par **jointure interne** (aucune valeur fabriquée).
- **PUE injecté** par région (config, pas de nombre magique). Sensibilité testée (monotone).
- **Dislocations** : `|basis| > z·std` → amplitude p95 + fraction du temps disloqué.
  **Persistance** : demi-vie AR(1) `ln(2)/−ln(φ)` (`None` si non mean-reverting).
- **Frontière réel/synthétique** : `energy_source` / `compute_source` loggués dans MLflow.

## Lancer

```bash
# tests P05 (jusqu'au patch testpaths de convergence, lancer explicitement)
uv run pytest projects/05_energy_compute_basis -q
uv run ruff check . && uv run mypy core

# pipeline complet + run MLflow + results/SYNTHESIS.md
uv run python projects/05_energy_compute_basis/src/run_basis.py
mlflow ui   # tableau de bord (experiment p05_energy_compute_basis)
```

> Données réelles : définir `ENTSOE_API_TOKEN` (énergie) ; sans token, repli synthétique
> déterministe **clairement étiqueté**. Le compute réel vient des snapshots P04 si accumulés.

## Résultats

- `results/SYNTHESIS.md` — amplitude du basis, sensibilité PUE, limites d'exécution (régénéré
  à chaque run).
- `results/RISK_REVIEW.md` — revue adversariale (look-ahead, faux arbitrage, hypothèse PUE,
  persistance, overfitting) + garde-fous avant tout signal tradable.

## Limites (PoC) & suite

PUE régional = hypothèse forte peu observable ; compute global → basis porté par l'énergie ;
coûts/latence de transfert ignorés. Palier institutionnel : routing de charge optimisé,
contraintes de capacité, données réelles, signal tradable hors-échantillon (cf. `RISK_REVIEW.md`).
