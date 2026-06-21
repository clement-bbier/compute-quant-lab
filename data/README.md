# Data — convention en 3 couches (versionnée DVC)

- `raw/`       brut, immuable, tel que pullé. **On n'écrit jamais ici à la main.**
- `interim/`   nettoyé / aligné dans le temps.
- `processed/` prêt-modèle (features), produit par les checks qualité.

Initialiser DVC : `dvc init` puis `dvc add data/raw/<source>` à chaque nouvel historique.
