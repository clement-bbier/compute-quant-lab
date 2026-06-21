# P04 — Indice spot compute + courbe forward simulée

Produit de données fondateur du labo : (1) un **indice spot compute** construit selon le
standard des meilleurs acteurs du marché, (2) une **courbe forward SIMULÉE** (Monte-Carlo
Rust) pour les futures compute CME annoncés mais non listés. Dont dépendront P03 (term
structure) et P06 (dérivés).

## Sources de données

| Jambe | Réel / Simulé | Source | Unité | Statut |
|---|---|---|---|---|
| Indice spot (PoC) | **Réel** | Snapshots marketplace Vast.ai/RunPod accumulés (`data/snapshots/`) | $/GPU·h | branché (collecteur token-gated) |
| Indice spot (canonique) | **Réel** | Silicon Data `SDH100RT` (settlement futures CME) | $/GPU·h | interface `SiliconDataSource` documentée, à brancher |
| Courbe forward | **SIMULÉE** | Modèle Schwartz un-facteur seedé sur le spot | $/GPU·h par échéance | branché (Rust + oracle Python) |

> ⚠️ **Frontière réel/simulé** : toute courbe forward porte `Curve.simulated = True` (champ
> obligatoire, sans défaut). Jamais servie comme un prix réel.

## Méthodologie de l'indice (standard marché)

Calage sur **GPU Markets** (public, reproductible) et **Silicon Data** (settlement CME) :

- estimateur **trimmed mean 20 %** + rejet des outliers à **2.5 MAD** (`method='trimmed_mean20+mad2.5'`) ;
- **no carry-forward**, fenêtre de staleness **24 h** (anti-survivorship) ;
- exclusion des list prices hyperscalers de l'estimateur ; séparation des `lease_type` ;
- fix strictement **point-in-time** (`snapshotted_at <= as_of`), âge du plus vieux relevé tracé.

Tout est **configurable** (pattern Strategy) : estimateur, filtre d'outliers, fenêtre,
sources exclues se permutent via `IndexConfig` sans modifier le cœur (`DEFAULT_INDEX_CONFIG`
= le standard ci-dessus).

## Courbe forward (Schwartz un-facteur)

`d ln S = κ(ln θ − ln S) dt + σ dW` (mean-reversion, commodité non stockable, analogie élec).
Moteur **Monte-Carlo Rust** (`forward_engine`, PyO3/maturin) pour la perf, **oracle Python
analytique** pour la parité (testée à 2 %). Calibration par défaut **OLS AR(1)** (standard
Schwartz) avec repli demi-vie robuste pour historique court.

## Plage, profondeur & anomalies (état PoC)

- **Profondeur snapshots** : la série propriétaire démarre à la **première exécution du
  collecteur** ; aucune profondeur rétroactive (le prix du compute n'a pas d'historique).
  À ce stade `data/snapshots/` est vide tant que `VASTAI_API_KEY` n'est pas fournie.
- **Historique de calibration** : tant que la série est mince, `run_build_curve.py` calibre
  sur un historique **synthétique étiqueté démo** ; à remplacer par la série réelle de
  l'indice une fois la collecte accumulée.
- **Anomalies traquées** : outliers (rejet MAD), offres fantômes/survivorship (no carry-forward),
  look-ahead (filtre point-in-time + test dédié), réel/simulé (flag + test).

## Lancer

```bash
uv sync --extra dev
# Moteur Rust (hors pyproject racine, zone protégée) :
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml
# Collecte d'un snapshot réel (nécessite VASTAI_API_KEY) :
uv run python -m infra.collectors.gpu_price_snapshot
# Construire + logger une courbe forward (MLflow) :
uv run python projects/04_compute_index_curve/run_build_curve.py
# Tests :
uv run pytest projects/04_compute_index_curve
```

## Reproductibilité

- **DVC** : `dvc add data/snapshots` (et `data/raw/<source>`) après chaque accumulation.
- **MLflow** : `build_forward_curve` logue modèle, moteur, calibrateur, seed, n_paths,
  κ/θ/σ + SHA git (`experiments/mlruns`, `mlflow ui`). MLflow 2026 → `MLFLOW_ALLOW_FILE_STORE=true`.
