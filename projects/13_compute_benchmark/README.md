# Compute Spot Benchmark — méthodologie publiable

> Le **prix de référence d'une GPU-heure**, par modèle, avec la **dispersion inter-venues**.
> Un auditeur externe doit pouvoir reconstruire l'indice à partir de cette page.

## 1. Ce que mesure le benchmark

À un instant de fix `t`, pour un modèle GPU (ex. H100), le benchmark publie :

1. **Indice canonique** `index(t)` — un prix unique `$/GPU·h` agrégeant les marketplaces.
2. **Dispersion inter-venues** — à quel point les venues s'écartent de cette référence
   (spread absolu, spread %, coefficient de variation) + **quelle venue est en moyenne
   moins chère** sur la fenêtre.

> **Frontière edge.** Le benchmark publie une **mesure**, pas une **décision**. La
> granularité est le **fix quotidien** ; aucun signal de timing live (« louer sur X
> maintenant ») n'est diffusé — cela relève d'une recherche privée séparée.

## 2. Données sous-jacentes (réelles, point-in-time)

- Source : snapshots des prix on-demand de marketplaces GPU (Vast.ai, RunPod) accumulés
  24/7, stockés dans un **cold store Parquet versionné** (`core.storage`, append-only,
  idempotent). Provenance `real_spot` — jamais simulé.
- Unité : **USD par GPU·heure**. Horodatages **UTC** tz-aware.
- ⚠️ **Historique court au début.** Le prix du compute n'a pas d'historique public profond :
  on l'accumule. L'indice est donc maigre au démarrage (cf. `results/benchmark_summary.md`),
  et grossit chaque jour. C'est assumé, pas masqué.

## 3. Construction de l'indice (méthode canonique)

Réutilise `core.ingestion.build_spot_index` (standard GPU Markets / Silicon Data, settlement
des futures compute CME). Pour un fix à `as_of` :

1. **Filtrage** : ne retenir que `gpu_model` voulu, `lease_type = on_demand`, hors list
   prices hyperscalers (AWS/GCP/Azure exclus de l'estimateur), et **point-in-time** —
   uniquement `snapshotted_at ≤ as_of`.
2. **Staleness (no carry-forward)** : ne garder que les relevés dans la fenêtre de 24 h
   précédant le fix. Une venue dont le dernier relevé est périmé est **ignorée**, pas reportée.
3. **Réduction par venue** : par marketplace, on prend la cohorte de relevés la plus fraîche
   et sa **médiane** (robuste au bruit d'une offre isolée ; disponibilité sommée).
4. **Rejet d'outliers** : filtre **MAD** (2.5 écarts absolus médians) sur les taux par venue.
5. **Agrégation** : **moyenne tronquée 20 %** des taux retenus → `index(t)`.

Chaque point porte ses métadonnées d'audit : `method`, `n_sources`, `oldest_obs_at`.
La méthode est **injectable** (`IndexConfig`) : estimateur, filtre, fenêtre permutables.

### Grille de fix
- **Produit publié** : fix **quotidien** à 00:30 UTC (`daily_fix_grid`). Le fix d'un jour
  *settle après coup* : la fenêtre de staleness de 24 h capture la journée écoulée.
- **Démo** : cadence par snapshot observé (`observed_fix_grid`) pour visualiser un historique
  maigre — clairement étiquetée « démo », ce n'est pas la granularité produit.

## 4. Dispersion inter-venues

Sur les venues **retenues par l'indice** (après rejet d'outliers), à chaque fix :

- `spread_abs = max − min` (`$/GPU·h`) ; `spread_pct = spread_abs / index(t)` ;
- `cv` = écart-type population / moyenne (coefficient de variation) ;
- `cheapest_venue` / `dearest_venue` (nommées).
- **Mono-venue** (`n_venues < 2`, ex. un modèle sur une seule marketplace) → dispersion
  **indéfinie** et flaggée (`is_defined = False`) : on ne fabrique pas une dispersion fictive.

**Niveaux moyens par venue** (`venue_levels`) : sur la fenêtre, niveau moyen `$/h` et
**escompte moyen vs indice** par venue nommée (négatif = moins cher que la référence). C'est
la réponse descriptive à « qui est moins cher en moyenne » — statique, jamais un signal live.

### Garde-fou anti-dérive
`dispersion` ré-implémente la réduction par-venue de l'indice (`core` étant en lecture seule).
Un test d'invariant garantit l'absence de dérive :
`estimator(filter(venue_rates_at(...))) == build_spot_index(...).price`.

## 5. Reproductibilité

`run_build_benchmark.py` logge un run **MLflow** (`compute_benchmark`) : paramètres
d'agrégation (méthode, staleness, fréquence de fix, fenêtre, modèles), métriques (nb de fix,
spread % moyen, état de l'historique), **SHA git** + **version DVC** des données, tag
`provenance=real_spot`. Le cold store versionné étant immuable, un run rejoué sur la même
version DVC est reproductible. Synthèse écrite dans `results/benchmark_summary.md`.

## 6. Lancer

```bash
# Peupler le cold store (ce worktree démarre vide) :
git checkout data-snapshots -- data/snapshots      # ou : dvc pull

uv run pytest -q projects/13_compute_benchmark/tests          # tests
uv run python projects/13_compute_benchmark/run_build_benchmark.py   # run + results/
uv run streamlit run projects/13_compute_benchmark/dashboard/app.py  # dashboard démo
```

## 7. Limites connues

- Historique court (quelques fix au démarrage) → série maigre ; séries et moyennes peu
  significatives statistiquement tant que l'accumulation est jeune.
- 2 venues seulement aujourd'hui (Vast.ai, RunPod) → la moyenne tronquée et le MAD ne filtrent
  pas encore ; l'indice = moyenne des deux médianes de venue. Robustesse réelle au-delà de 3 venues.
- Survivorship des venues : une marketplace qui disparaît biaise l'historique (à surveiller).
- `on_demand` uniquement (spot/reserved non agrégés — standard, jamais mélanger les baux).
