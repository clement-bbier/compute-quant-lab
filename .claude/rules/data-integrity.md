---
paths:
  - "core/ingestion/**"
  - "core/data_quality/**"
  - "data/**"
---
# Intégrité des données

- `data/raw/` est IMMUABLE. On n'y écrit jamais à la main ni par script post-ingestion.
  Toute transformation produit un nouvel artefact dans `data/interim/`.
- Tous les timestamps sont en UTC, timezone-aware. Pas de datetime naïf.
- Toute série ingérée est versionnée via DVC avant d'être utilisée par un projet.
- Documenter pour chaque source : unité, fuseau, fréquence, méthode de gap-filling.
- Aucune donnée révisée rétroactivement ne doit écraser une valeur historique
  (préserver le point-in-time).
