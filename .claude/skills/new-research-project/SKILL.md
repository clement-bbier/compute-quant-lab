---
name: new-research-project
description: Scaffolde un nouveau projet de recherche dans projects/ avec la structure standard du labo. À invoquer pour démarrer un projet (ex. "nouveau projet sur la volatilité des prix GPU").
---
# New Research Project

1. Demander un numéro/nom court (ex. `02_gpu_vol_term_structure`).
2. Créer `projects/NN_nom/` avec : `CLAUDE.md`, `src/`, `notebooks/`, `results/`, `dashboard/`.
3. Le `CLAUDE.md` local décrit : la thèse spécifique, les données utilisées, l'état
   d'avancement, les résultats clés. Il ne duplique PAS le glossaire global.
4. Réutiliser `core/` au maximum ; ce qui devient générique remonte dans `core/`.
5. Ajouter une ligne au §4 "index des projets" du CLAUDE.md racine.
