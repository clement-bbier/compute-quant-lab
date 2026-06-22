"""Couche vitrine P13 — benchmark spot compute public (indice + dispersion).

Consomme **uniquement** la fondation (`core.storage` pour lire le cold store,
`core.ingestion.build_spot_index` pour l'agrégation canonique). Aucune réécriture de
``core`` : que de la consommation. Logique de calcul pure ici ; l'I/O (lecture du lac,
dashboard, MLflow) vit dans ``run_build_benchmark.py`` et ``dashboard/app.py``.

Frontière edge (vitrine PUBLIQUE) : on publie la **mesure** (prix de référence quotidien
+ dispersion inter-venues descriptive), jamais la **décision** de timing (« louer sur X
maintenant »). Cf. ``projects/13_compute_benchmark/CLAUDE.md`` §frontière edge.
"""
