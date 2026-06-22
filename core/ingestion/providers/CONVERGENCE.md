# W1 — providers_foundation · handoffs convergence

> Ce lot écrit **uniquement** dans `core/ingestion/providers/` (nouveau) + `core/ingestion/gpu_market.py`
> (→ shim). Tout ce qui touche la **zone protégée** (`pyproject.toml`, `.github/`, `.claude/`) ou un
> autre module est listé ici pour la session de convergence — **non appliqué** dans ce worktree.

## 1. CI / `testpaths` (zone protégée — `.github/`, `pyproject.toml`)
Les nouveaux tests vivent sous **`core/ingestion/providers/tests`** (seul emplacement autorisé pour ce
lot). Ils ne sont **pas** ramassés par la CI actuelle ni par `testpaths` :
- **`.github/workflows/ci.yml`** : ajouter `core/ingestion/providers/tests` à la boucle d'isolation
  (`for d in tests core/backtest/tests … core/storage/tests projects/*/tests; do …`).
- (Optionnel) **`pyproject.toml`** `[tool.pytest.ini_options]` : sans objet tant que la CI lance chaque
  dossier en isolation ; ne **pas** mettre plusieurs `core/*/tests` dans un même `testpaths` (collision
  de module `conftest`, cf. note pyproject).

Vérif locale (ce worktree, vert) :
```bash
uv run pytest -q core/ingestion/providers/tests        # 14 passed
uv run pytest -q projects/04_compute_index_curve/tests/test_gpu_market.py   # 4 passed (non-régression)
uv run pytest -q core/storage/tests/test_collector_rewire.py               # 2 passed (collecteur intact)
uv run ruff check . && uv run mypy core                # verts (100 fichiers)
```

## 2. Refactor livré (non destructif)
- `core/ingestion/gpu_market.py` est désormais un **shim** : il ré-exporte `normalize_gpu_model`,
  `parse_vastai_offers`, `fetch_vastai`, `parse_runpod_gpu_types`, `fetch_runpod`, et
  `fetch_live_gpu_prices` délègue au registre `core.ingestion.providers.fetch_all`.
- **Aucun changement de comportement runtime** : même signature `fetch_live_gpu_prices(now=None)`,
  même défaut `utcnow`, même ordre (vastai → runpod), même `RuntimeError` (message verbatim) si rien
  n'est configuré, même `Snapshot`. La collecte live (GitHub Actions) tourne à l'identique.
- **Seul écart, cosmétique** : le `logger.warning` des clés absentes est générique
  (`"VASTAI_API_KEY absent : provider 'vastai' ignoré."`) et émis par le logger
  `core.ingestion.providers` (au lieu de `core.ingestion.gpu_market`). Aucun test n'asserte ce texte ;
  ce n'est pas un contrat de comportement.
- `core/ingestion/__init__.py` (hors module possédé, **non touché**) continue d'importer ses symboles
  depuis le shim : la façade `core.ingestion` reste intacte.

## 3. Dépendances
Aucune nouvelle dépendance (`requests` déjà présent dans `pyproject.toml`). Rien à ajouter au lockfile.

## 4. Aval — vague W2 (1 instance = 1 venue)
La fondation est prête. Ajouter une venue = **3 étapes** (documentées dans
`core/ingestion/providers/__init__.py`) :
1. `core/ingestion/providers/<venue>.py` : `parse_<venue>` (pur) + `fetch_<venue>` (I/O token-gated) +
   classe `<Venue>Provider` (`name`, `required_env`, `fetch(now)`), réutilisant `base.normalize_gpu_model`.
2. Ajouter `<Venue>Provider()` au tuple `PROVIDERS`.
3. Test de parité sous `tests/` + (convergence) clé en **Secrets GitHub** pour le collecteur always-on.

Chaque venue W2 écrit dans son propre fichier → zéro collision de merge.
