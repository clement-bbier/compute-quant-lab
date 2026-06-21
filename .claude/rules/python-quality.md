---
paths:
  - "**/*.py"
---
# Qualité du code Python

- Type hints obligatoires sur toute fonction publique. `mypy core` doit passer.
- Pas de nombre magique : les constantes (PUE, conso GPU, etc.) vivent dans un module
  de config ou sont des arguments nommés, jamais codées en dur dans la logique.
- Docstrings courtes au format NumPy sur les fonctions de `core/`.
- Pas de `print` pour le logging : utiliser `core.utils.logging`.
- Fonctions pures côté `core/` (pas d'effet de bord I/O caché) ; l'I/O est explicite.
