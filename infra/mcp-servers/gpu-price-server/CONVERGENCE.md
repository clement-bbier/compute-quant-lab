# Convergence handoff — gpu-price MCP server

The module was written **without touching the protected zone** (parallel-ops §7). To apply during convergence:

1. **`pyproject.toml`**: add `"mcp>=1.2"` to `[project].dependencies`.
   (In dev, `mcp` is installed ad hoc via `uv pip install mcp`.)
2. **`.github/workflows/ci.yml`**: add a matrix job for
   `infra/mcp-servers/gpu-price-server/tests`, the way the W1 convergence did for
   `core/ingestion/providers/tests`. **Do not modify `testpaths`** (stays `["tests"]`).
3. **`.mcp.json`**: already wired (`gpu-price` -> `python … server.py`), no change needed.

Independence: the server reads the storage layer and never calls `fetch_live_gpu_prices`
or the W1 providers layer — no code coordination is required.
