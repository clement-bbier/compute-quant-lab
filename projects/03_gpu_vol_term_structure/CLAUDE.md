# Projet 03 — GPU Volatility & Term Structure

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo et état :
> [README.md](README.md).

## Thèse spécifique
La **volatilité** des prix GPU est un actif en soi, et la **structure par terme** de la
courbe forward (contango/backwardation) porte de l'information directionnelle. P03 estime
la vol réalisée de l'indice spot compute et analyse la term structure de la forward SIMULÉE.

## Modules possédés
- `projects/03_gpu_vol_term_structure/` UNIQUEMENT.
- Interdit (lecture seule) : tout `core/`, zone protégée racine (`CLAUDE.md`, `.claude/`,
  `.mcp.json`, `pyproject.toml`). Promotions vers `core/` → patches convergence.

## Dépendances amont (P04, dans `main`)
- **Indice spot RÉEL** : `core.ingestion.build_spot_index` (un fix point-in-time par `as_of`).
- **Forward SIMULÉE** : `projects/04_compute_index_curve/src/forward` (Schwartz 1-facteur),
  consommée via insertion `sys.path` (import `forward.build_curve`). ⚠️ jamais réelle.

## Architecture (SOLID / DI, logique pure)
- **Vol** : `VolEstimator` (Protocol) → `RealizedVol`, `EwmaVol` (numpy pur, causals).
  GARCH = point d'extension documenté (pas de dép `arch` sans convergence).
- **Term structure** : `TermStructureAnalyzer` pur → `TermStructure` (pente/courbure/forme).
- **Signal** : `directional_signal` (convention roll-yield : backwardation→long).
- **Glue** : `spot_series.build_spot_series` rejoue `build_spot_index` sur une grille.

## Frontière réel/simulé (non négociable)
`TermStructure.simulated` est OBLIGATOIRE (sans défaut), propagé dans `DirectionalSignal`.
Tout ce qui dérive de la forward est `simulated=True`. Test dédié (`test_simulated_flag.py`)
échoue si le drapeau est absent (rule `forward-real-simulated`).

## État d'avancement (PoC-now)
- [x] Estimateurs de vol réalisée + EWMA (numpy pur), anti look-ahead testé
- [x] Analyse de term structure (pente/courbure/forme contango/backwardation)
- [x] Signal directionnel roll-yield (backwardation→long)
- [x] Glue série spot point-in-time (consomme `core.ingestion`)
- [x] `run_analysis.py` : run MLflow loggué + synthèse `results/`
- [ ] GARCH (palier institutionnel, convergence pour la dép `arch`)
- [ ] Calibrer sur la série spot réelle une fois les snapshots accumulés
- [ ] Promouvoir `VolEstimator`/estimateurs vers `core/` (convergence)

## Résultats clés
Vol réalisée/EWMA de l'indice spot + forme de la term structure de la forward SIMULÉE
(+ signal), run MLflow rejouable. Détails : [README.md](README.md) / [results/](results/).
