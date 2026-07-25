# Data — convention en couches

- `snapshots/` brut collecté heure par heure (prix GPU multi-venues).
  **Versionné dans git** : les CSV via git-LFS, les Parquet en git ordinaire.
  C'est la seule couche irremplaçable — le prix du compute n'a pas
  d'historique achetable, il ne s'obtient qu'en l'accumulant.
- `raw/`       brut d'une source externe, immuable. **On n'écrit jamais ici à la main.**
- `interim/`   nettoyé / aligné dans le temps.
- `processed/` prêt-modèle (features), produit par les checks qualité.
- `cold/`      cold store dérivé (Parquet partitionné), régénérable.

Les couches dérivées (`raw/`, `interim/`, `processed/`, `cold/`) ne sont pas
versionnées : elles se reconstruisent depuis `snapshots/` et les connecteurs.

Récupérer les données après un clone : `git lfs pull`.
