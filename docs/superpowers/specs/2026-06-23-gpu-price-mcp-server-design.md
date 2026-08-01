# Design — `gpu-price` MCP server

> Date: 2026-06-23 · Status: validated in brainstorming, pending user review
> Author: research director session (Claude) · Target: `infra/mcp-servers/gpu-price-server/`

## 1. Context & goal

The `infra/mcp-servers/gpu-price-server/` directory only contains a
`.gitkeep`: the server is **declared** in `.mcp.json` (`command: python …
server.py`) but **not implemented**, so it starts neither in Claude Code nor in VSCode.

The collector
[infra/collectors/gpu_price_snapshot.py](../../../infra/collectors/gpu_price_snapshot.py)
already accumulates the GPU rental price history in `data/snapshots/` (CSV
**and** partitioned Parquet lake, double write). **Goal**: expose this real
history through an MCP server so that an agent (Claude Code, VSCode agent
mode) can query it in natural language — latest price, history, stats, SQL
query — while respecting point-in-time.

## 2. Scope

**In scope**
- 5 read-only MCP tools over the Parquet lake (`data/snapshots/`).
- Optional point-in-time (`as_of`) on the structured tools.
- TDD test harness (pure logic isolated from the MCP framework).
- Adding the `mcp` dependency and aligning `testpaths`.

**Out of scope**
- The `energy-data` server (separate batch, depends on the ENTSO-E connector).
- Canonical spot index aggregation (P04) — the server serves the **raw**
  data, not the index.
- Any backend other than the Parquet cold store (TickStream/HotCache remain stubs).
- Mirroring into VSCode's native `mcp.json` (next step, once the server is proven).

## 3. Decisions made (brainstorming)

| # | Decision | Choice made |
|---|----------|--------------|
| Q1 | Surface | **Rich**: `latest_price`, `price_history`, `list_gpu_models`, `summary_stats`, `query` (SQL) |
| Q2 | Point-in-time | **`as_of` optional everywhere** (default = now) |
| Q3 | SQL security | **Full DuckDB** via `core.storage.query` (risk accepted, documented) |
| Arch | Structure | **Approach 1**: thin server + testable pure service |
| Instruction | Tests | "test thoroughly that it works" -> serious TDD, point-in-time proven |

## 4. Architecture & components

Approach 1 — business logic is isolated from the MCP framework so it is
testable without starting the server (follows "pure functions on the core
side, explicit I/O" from `python-quality.md`).

```
infra/mcp-servers/gpu-price-server/
├── service.py    # PURE logic: receives an injected PriceStore, returns JSON-serializable dicts. NO mcp import.
├── server.py     # FastMCP: 5 @mcp.tool() delegating to service.py + data/snapshots path resolution + stdio transport.
├── tests/
│   └── test_service.py   # TDD: ParquetPriceStore on tmp_path + deterministic synthetic data
├── README.md     # provenance: unit ($/GPU·h), timezone (UTC), frequency (hourly snapshot), real/simulated
└── CONVERGENCE.md  # protected-zone handoff: pyproject (mcp) + CI matrix (see section 10), like W1
```

- **Reads**: `core.storage.ParquetPriceStore(<root>)` — `read(as_of=…,
  source=…)` already bounds to point-in-time and rejects a naive `as_of`.
- **Root resolution** in `server.py`: `os.environ["CLAUDE_PROJECT_DIR"]` if
  present, else `Path(__file__).resolve().parents[3]`, then `/ "data" / "snapshots"`.
- **Injection**: `service.py` only knows the **Protocol** `PriceStore`.
  Tests inject a temporary store; `server.py` injects the real Parquet
  store. (DI / OCP, the lab's usual pattern.)

## 5. Tool API

Every response carries `"provenance": "real"` (genuine observed spot data —
`forward-real-simulated.md` rule) and the **effective** `as_of`. Every
`service.py` function is pure: `(store, …) -> dict`.

### 5.1 `list_gpu_models(store, *, as_of=None) -> list[str]`
Sorted list of distinct `gpu_model` present in the lake (bounded to `snapshotted_at <= as_of`).

### 5.2 `latest_price(store, gpu_model, *, lease_type="on_demand", as_of=None) -> dict`
For each `source`, the freshest observation (`max snapshotted_at <= as_of`) for the model/lease.
```json
{
  "gpu_model": "H100", "lease_type": "on_demand", "as_of": "2026-06-21T13:54:59+00:00",
  "provenance": "real", "found": true,
  "by_source": [{"source": "vastai", "price_usd_per_hour": 2.13, "availability": 4,
                 "snapshotted_at": "2026-06-21T13:54:59+00:00"}],
  "summary": {"min": 2.13, "median": 2.13, "max": 2.13, "n_sources": 1}
}
```
Unknown model -> `{"found": false, "message": "...", "available_models": [...]}`.

### 5.3 `price_history(store, gpu_model, *, start=None, as_of=None, source=None, lease_type=None) -> dict`
Time series in ascending order. `as_of` bounds the top (point-in-time), `start` bounds the bottom.
```json
{"gpu_model": "H100", "start": null, "as_of": "...", "provenance": "real", "n": 42,
 "observations": [{"snapshotted_at": "...", "source": "vastai", "lease_type": "on_demand",
                   "price_usd_per_hour": 2.13, "availability": 4}]}
```

### 5.4 `summary_stats(store, gpu_model, *, lease_type=None, as_of=None) -> dict`
Descriptive stats over the observations (bounded to point-in-time).
```json
{"gpu_model": "H100", "as_of": "...", "provenance": "real", "n": 42,
 "overall": {"count": 42, "min": 1.9, "max": 2.4, "mean": 2.11, "median": 2.13, "std": 0.08},
 "by_source": [{"source": "vastai", "count": 42, "min": 1.9, "max": 2.4, "mean": 2.11, "median": 2.13}],
 "first_obs_at": "...", "last_obs_at": "..."}
```

### 5.5 `query(store, sql) -> dict`
Delegates to `core.storage.query(sql, store)` (the `prices` view = the
lake). Returns the rows.
```json
{"columns": ["gpu_model", "n"], "rows": [{"gpu_model": "H100", "n": 42}], "n": 1,
 "note": "raw DuckDB SQL — NO point-in-time guard, as_of filtering is the query's responsibility"}
```

## 6. Point-in-time semantics (anti look-ahead)

- `as_of` received as an **ISO string** through MCP -> parsed into a
  `datetime`. **Naive rejected** with an explicit message ("provide a
  tz-aware UTC instant, e.g. `2026-06-21T00:00:00+00:00`"). Consistent with
  `ParquetPriceStore.read` and the `data-integrity.md` rule.
- `as_of` absent -> "now" = the entire available history. The effective
  `as_of` returned is then the observed `max(snapshotted_at)` (auditable).
- The 4 structured tools bound to `snapshotted_at <= as_of`. **`query` does
  not apply it** (raw lake) — explicit `note` in the response + README.

## 7. Security (risk accepted: full DuckDB)

- `query` reuses `core.storage.query` **as is**: in-memory DuckDB
  connection, `prices` view, but **the full power of DuckDB** remains
  accessible (`read_csv('C:/…')`, `COPY … TO`, `INSTALL httpfs`).
- **Risk**: the server is driven by an LLM; a prompt injection could
  generate a destructive or exfiltrating query. **Explicit user decision**,
  documented in the README and the tool's docstring ("only expose this
  server to trusted agents").
- **Deferred mitigation** (not implemented, noted for later): SELECT-only
  sandbox mode / disabling file access. To revisit if the server is exposed
  outside the local machine.

## 8. Error handling

- Unknown `gpu_model` -> `found: false` response + `available_models` (no
  exception: guides the LLM).
- Empty lake -> empty/neutral responses (handled by `ParquetPriceStore.read`).
- Naive `as_of` / invalid ISO -> `ValueError` -> `server.py` returns a readable MCP tool error.
- DuckDB SQL error -> message propagated in the `query` tool's response.

## 9. Data & provenance (README)

| Attribute | Value |
|---|---|
| Unit | USD per GPU-hour ($/GPU·h) |
| Timezone | UTC, tz-aware (naive datetime forbidden) |
| Frequency | scheduled snapshot (hourly, Task Scheduler / GitHub Actions) |
| Sources | marketplaces (vastai, …; `source` field) |
| Real/simulated | **real** (observed spot) — no simulated series served here |
| Backend | partitioned Parquet lake `source=/month=` under `data/snapshots/` (tracked as plain git files) |

## 10. Dependencies & integration (protected zone -> convergence)

Branch built on `main` post-W1 (`209fab1`). The server is **independent of
the W1 providers layer**: it reads storage, never calls
`fetch_live_gpu_prices` nor the providers. Files in the **protected zone**
(`pyproject.toml`, `.github/workflows/ci.yml`) only go through **convergence**
(parallel-ops section 7) — so **documented in `CONVERGENCE.md`, NOT applied
in the branch**, exactly like W1:

- **`pyproject.toml`** (handoff): add `"mcp>=1.2"` to `dependencies`. For
  local dev/test, `mcp` is installed **ad hoc** in the `.venv` (`uv pip
  install mcp`), like `duckdb` was for P11.
- **`.github/workflows/ci.yml`** (handoff): add
  `infra/mcp-servers/gpu-price-server/tests` to the **CI matrix** (1
  isolated job), like convergence did for `core/ingestion/providers/tests` in W1.
  **`testpaths` stays `["tests"]`** — not modified (the lab's actual pattern, confirmed by `209fab1`).
- **`.mcp.json`**: **already wired** (`gpu-price` -> `python … server.py`),
  protected zone but no change required; the server will start as soon as the code is written.

Locally, the server's test suite runs via an explicit path: `pytest infra/mcp-servers/gpu-price-server/tests`.

## 11. Test strategy (TDD)

Tests written **before** the code. `test_service.py` sets up a
`ParquetPriceStore(tmp_path)`, writes **deterministic** synthetic snapshots
into it (>= 2 sources, >= 2 models, >= 2 instants), then verifies:

1. `list_gpu_models` -> distinct, sorted, bounded by `as_of`.
2. `latest_price` -> freshest observation **per source**, exact min/median/max summary, `as_of` respected.
3. `price_history` -> ascending order, `start`/`as_of` bounds, `source`/`lease_type` filter.
4. `summary_stats` -> exact count/min/max/mean/median/std on known data + per-source breakdown.
5. **Point-in-time**: an observation later than `as_of` is **excluded** (dedicated anti look-ahead test).
6. Naive `as_of` -> `ValueError`; invalid ISO `as_of` -> clear error.
7. Unknown `gpu_model` -> `found: false` + `available_models`.
8. `query` -> a `SELECT count(*) … GROUP BY gpu_model` returns the right number of rows.
9. **Smoke test** for `server.py`: import succeeds and the 5 tools are registered on the FastMCP instance.

## 12. Acceptance criteria

- [ ] `pytest infra/mcp-servers/gpu-price-server/tests` green (CI integration = convergence handoff, see section 10).
- [ ] `ruff check .` and `mypy` green on the new code (type hints + NumPy docstrings).
- [ ] The server starts over stdio and exposes 5 tools (verified by the smoke test).
- [ ] A manual "latest H100 price" query returns a value consistent with `data/snapshots/`.
- [ ] The point-in-time test proves the exclusion of observations later than `as_of`.

## 13. Next (out of batch)

- Mirror the servers into VSCode's native `mcp.json` (`${workspaceFolder}`, `envFile`).
- `energy-data` server (ENTSO-E).
- Possible SQL sandbox mode if exposed outside the local machine.
