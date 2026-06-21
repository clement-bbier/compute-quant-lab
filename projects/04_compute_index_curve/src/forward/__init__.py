"""Jambe forward de P04 : courbe forward compute SIMULÉE (Schwartz un-facteur).

Sous-modules : ``models`` (types), ``protocols`` (Strategy/DI), ``oracle`` (analytique +
MC Python), ``engine`` (MC Rust), ``calibrators`` (estimation des params), ``build_curve``
(orchestration MLflow/DVC). Toute courbe produite ici est ``simulated=True``.
"""
