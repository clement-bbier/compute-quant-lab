# Handoff convergence — serveur MCP gpu-price

Le module a été écrit **sans toucher la zone protégée** (parallel-ops §7). À appliquer en convergence :

1. **`pyproject.toml`** : ajouter `"mcp>=1.2"` aux `[project].dependencies`.
   (En dev, `mcp` est installé ad-hoc via `uv pip install mcp`.)
2. **`.github/workflows/ci.yml`** : ajouter un job de matrice sur
   `infra/mcp-servers/gpu-price-server/tests`, comme la convergence W1 l'a fait pour
   `core/ingestion/providers/tests`. **Ne pas modifier `testpaths`** (reste `["tests"]`).
3. **`.mcp.json`** : déjà câblé (`gpu-price` → `python … server.py`), aucun changement.

Indépendance : le serveur lit la couche storage et n'appelle jamais `fetch_live_gpu_prices`
ni la couche providers W1 — aucune coordination de code requise.
