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
  (orchestration + MLflow + DVC).

## Reproductibilité
Run MLflow via `core.utils.tracking.run` (params : variables, lags de publication,
fenêtres, seed ; tags SHA + DVC). Brut exogène → `data/raw/exogenous/` versionné DVC.

## État d'avancement (PoC-now ✅)
- [x] Mécanique point-in-time (lag + révisions) dans `core/features/` + 16 tests.
- [x] Anti look-ahead STRICT testé en rouge (lag de publication, garde-fou).
- [x] Builders point-in-time (lags, moyennes mobiles, diffs) sur fixtures connues.
- [x] Mesure du lead anti-overfit : cross-corrélation + OLS out-of-sample (split temporel).
- [x] Run MLflow reproductible + brut DVC (cache local ; pointeur cf. CONVERGENCE).

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
Patchs zone protégée (testpaths, .gitignore DVC, registre sources…) :
voir [CONVERGENCE.md](CONVERGENCE.md).
