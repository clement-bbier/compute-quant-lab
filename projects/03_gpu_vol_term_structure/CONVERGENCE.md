# P03 → Handoff convergence

Éléments touchant la **zone protégée** (interdite au worktree périphérique). À traiter par
la session de convergence lors du merge `feature/P03-gpu_vol_term_structure` → `integration`.

## 1. `pyproject.toml` — `testpaths` (requis)
`[tool.pytest.ini_options].testpaths` n'inclut pas `projects/03`. Ajouter l'entrée pour que
la CI ramasse la suite P03 (comme déjà fait pour P04) :

```toml
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/03_gpu_vol_term_structure/tests",  # <- ajout P03
]
```

En attendant : gate local via chemin explicite — `pytest -q projects/03_gpu_vol_term_structure`.

## 2. Promotion éventuelle vers `core/` (à décider)
`VolEstimator` (Protocol) + `RealizedVol`/`EwmaVol` sont **génériques** (aucune dépendance
au compute) : candidats à une promotion `core/features/volatility.py` (réutilisables par
P02/P05). Garder dans `projects/03` tant qu'un second consommateur n'est pas avéré (PoC →
fondation). Décision = convergence.

## 3. Dépendance `arch` (GARCH) — NON ajoutée
Le palier institutionnel (GARCH) nécessiterait `arch` dans `pyproject.toml` (zone protégée).
Volontairement différé (conforme à l'instruction « éviter une dép neuve sans convergence ») ;
le `VolEstimator` (Protocol) est prêt à l'accueillir sans toucher aux consommateurs.

## 4. Consommation cross-projet de la forward P04
`run_analysis.py` importe le paquet `forward` de P04 via insertion `sys.path` de
`projects/04_compute_index_curve/src` (la logique testée, elle, reste pure et n'en dépend
pas). Si la forward est promue vers `core/pricing/curve/` (handoff P04), remplacer cet
import par l'import `core` — sans changement de la logique d'analyse.
