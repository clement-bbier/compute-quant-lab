# Projet 07 — Exogenous Macro Signal

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine.

## Thèse spécifique
Des variables **exogènes** (prix du gaz, météo HDD/CDD) **précèdent** les mouvements
de la jambe énergie, donc du spark spread (P01). P07 fabrique ces features
**point-in-time** dans `core/features/` (réutilisables par P09 ML) et mesure leur
*lead* sur le spread — sans look-ahead ni sur-fitting.

## Risque n°1 : le LOOK-AHEAD (données macro retardées + révisées)
Chaque observation porte deux horodatages : `value_ts` (période décrite) et
`knowledge_ts = value_ts + lag de publication` (date de publication). Une feature à
`t` n'utilise que `knowledge_ts <= t`. Les **révisions** = plusieurs millésimes par
`value_ts` ; à `t` on ne voit que le dernier publié à temps. Modélisé dans
`core.features.as_of_snapshot`, **testé en rouge** (`core/features/tests`).

## Architecture
- `core/features/` (module possédé, fondation) : `protocols.py` (contrats vintage,
  `ExogenousSource`, `FeatureBuilder`), `builders.py` (`as_of_snapshot`,
  `from_lagged_series`, garde-fou `assert_point_in_time`, transforms purs,
  `PointInTimeFeatureBuilder`).
- `projects/07_…/src/` : `sources.py` (I/O, repli synthétique déterministe),
  `analysis.py` (cross-corrélation + OLS de confirmation, purs), `run_signal.py`
  (orchestration + MLflow).

## Reproductibilité
Run MLflow via `core.utils.tracking.run` (params : variables, lags de publication,
fenêtres, seed ; tags SHA + DVC). Brut exogène → `data/raw/exogenous/`, cache local
(gitignoré par design, jamais committé).

## Branche ERCOT (L0 grid-stress, données RÉELLES)
Sous-pipeline distinct du signal gaz/HDD/CDD ci-dessus : mesure si la **marge de réserve**
et le **gradient net-load** ERCOT (prédicteurs gelés du pré-enregistrement L0,
`docs/superpowers/specs/2026-06-23-L0-ercot-grid-stress-preregistration.md`) prédisent un
spike RTM, hors échantillon.
- `src/ercot_dataset.py` (97 L) — reconstruit les prédicteurs point-in-time depuis le cold
  store (`as_of ≈ 18h CPT J-1`), garde-fou anti look-ahead sur `publish_time <= as_of`.
- `src/ercot_labels.py` (67 L) — labels spike (percentile intra-jour, seuil absolu).
- `src/ercot_baseline.py` (46 L) — baseline climatologique de référence.
- `src/ercot_calibration.py` (98 L) — purged K-fold + embargo (`core.models`), comparaison
  à la baseline, IC bootstrap + correction Benjamini-Hochberg multi-specs.
- `src/ercot_eval.py` (79 L) — métriques PR-AUC + tests statistiques.
- `src/run_ercot_calibration.py` (70 L) — orchestration → run MLflow.
- 448 LOC au total, 14 tests dédiés dans `tests/test_ercot_*.py`.

Lit **exclusivement** le cold store ERCOT réel (`data/cold/ercot`, rule
`training-cold-store`) — jamais de repli synthétique, contrairement au reste de P07.
Ce worktree ne contient pas le cold store peuplé (`data/cold/` est vide hors `.gitkeep`) :
les 14 tests passent sur fixtures, mais `run_ercot_calibration.py` a besoin d'un backfill
réel au préalable (`infra/collectors/ercot_backfill.py --start ... --end ...`, nécessite
`GRIDSTATUS_API_KEY`).

## État d'avancement (PoC-now ✅)
- [x] Mécanique point-in-time (lag + révisions) dans `core/features/` + 16 tests.
- [x] Anti look-ahead STRICT testé en rouge (lag de publication, garde-fou).
- [x] Builders point-in-time (lags, moyennes mobiles, diffs) sur fixtures connues.
- [x] Mesure du lead anti-overfit : cross-corrélation + OLS out-of-sample (split temporel).
- [x] Run MLflow reproductible + brut exogène en cache local (`data/raw/`, cf. CONVERGENCE).

## Résultats clés (données SIMULÉES, seed=7)
DGP injectant un lead de 3 j ; le pipeline retrouve **2 j exploitables** (le lag de
publication d'1 j rogne 1 j d'avance) :
- meilleure feature **gas_price_lag0**, lead **2 j**, **|corr| ≈ 0.65** ;
- `hdd_lag0` confirme (≈ 0.65) ; `cdd` ≈ 0 (contrôle négatif cohérent) ;
- OLS confirmation : coef < 0, p-value ≈ 4e-45, **R²_oos ≈ 0.35** (prédictif, non sur-fitté).

**Pièges couverts** : lag de publication (test rouge), révisions (vintages), fuseau UTC,
régression fallacieuse (mesure sur les **variations**, pas les niveaux).
**Hors périmètre (institutionnel)** : connecteur réel météo/gaz (`data-engineer`),
nowcasting, modèle causal, panel large, gestion fine des révisions réelles.

## Convergence
Patchs zone protégée (testpaths, registre sources…) :
voir [CONVERGENCE.md](CONVERGENCE.md).
