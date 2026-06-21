# Projet 04 — Compute Index & Forward Curve

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo détaillée
> et état : [README.md](README.md).

## Thèse spécifique
Le prix du compute n'a pas d'historique profond : le fabriquer. Construire (a) l'indice
spot compute canonique (standard Silicon Data / GPU Markets, settlement des futures CME)
et (b) une courbe forward SIMULÉE pour les futures compute CME non listés. Produit de
données fondateur dont dépendent P03 (term structure) et P06 (dérivés).

## Modules possédés
- `core/ingestion/` (jambe compute) · `infra/collectors/` · `projects/04_compute_index_curve/`.
- Interdit : `core/pricing/` (P01), zone protégée racine. → patches convergence.

## Architecture (SOLID / configurable)
- **Sources** : `ComputeIndexSource` → `MarketplaceProxySource` (réel, PoC), `SiliconDataSource` (stub canonique).
- **Agrégation** : `IndexEstimator` + `OutlierFilter` (Strategy) → `DEFAULT_INDEX_CONFIG` = standard marché.
- **Forward** : `ForwardCurveModel` (Rust MC / oracle Python) + `ForwardCalibrator` (OLS AR(1) / demi-vie).
- Tout permutable par injection (`IndexConfig`, `build_forward_curve(...)`) sans toucher le cœur.

## Frontière réel/simulé (non négociable)
`Curve.simulated` est obligatoire (sans défaut). Forward = toujours simulée. Spot = réel
(marketplace) ou canonique (Silicon Data). Tests dédiés garantissent l'invariant.

## État d'avancement
- [x] Types + protocoles + stratégies d'agrégation (trimmed mean 20 % + 2.5 MAD, configurable)
- [x] `build_spot_index` point-in-time, no carry-forward, anti look-ahead (testé)
- [x] `CsvSnapshotStore` idempotent + collecteur réécrit (Vast.ai token-gated)
- [x] Forward Schwartz : oracle Python analytique + MC, moteur Rust (parité 2 %)
- [x] Calibration OLS AR(1) (+ repli demi-vie), orchestration MLflow
- [ ] Brancher Silicon Data (SDH100RT) — spec API + token
- [ ] Accumuler la série snapshots réelle (cron) puis calibrer sur l'indice réel
- [ ] Promouvoir la forward dans `core/pricing/curve/` (convergence, après P01)

## Résultats clés
Courbe forward SIMULÉE générée bout-en-bout (moteur Rust, OLS AR(1)), convergente au spot
à τ=0, run MLflow rejouable (params + SHA git). Détails : [README.md](README.md).
