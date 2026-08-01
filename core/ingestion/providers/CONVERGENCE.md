# W1 -- providers_foundation - convergence handoffs

> This batch writes **only** into `core/ingestion/providers/` (new) + `core/ingestion/gpu_market.py`
> (-> shim). Everything touching the **protected zone** (`pyproject.toml`, `.github/`, `.claude/`) or
> another module is listed here for the convergence session -- **not applied** in this worktree.

## 1. CI / `testpaths` (protected zone -- `.github/`, `pyproject.toml`)
The new tests live under **`core/ingestion/providers/tests`** (the only location allowed for this
batch). They are **not** picked up by the current CI nor by `testpaths`:
- **`.github/workflows/ci.yml`**: add `core/ingestion/providers/tests` to the isolation loop
  (`for d in tests core/backtest/tests ... core/storage/tests projects/*/tests; do ...`).
- (Optional) **`pyproject.toml`** `[tool.pytest.ini_options]`: moot as long as the CI runs each
  directory in isolation; do **not** put several `core/*/tests` in the same `testpaths` (`conftest`
  module collision, see the pyproject note).

Local check (this worktree, green):
```bash
uv run pytest -q core/ingestion/providers/tests        # 14 passed
uv run pytest -q projects/04_compute_index_curve/tests/test_gpu_market.py   # 4 passed (non-regression)
uv run pytest -q core/storage/tests/test_collector_rewire.py               # 2 passed (collector intact)
uv run ruff check . && uv run mypy core                # green (100 files)
```

## 2. Refactor delivered (non-destructive)
- `core/ingestion/gpu_market.py` is now a **shim**: it re-exports `normalize_gpu_model`,
  `parse_vastai_offers`, `fetch_vastai`, `parse_runpod_gpu_types`, `fetch_runpod`, and
  `fetch_live_gpu_prices` delegates to the `core.ingestion.providers.fetch_all` registry.
- **No runtime behaviour change**: same `fetch_live_gpu_prices(now=None)` signature, same `utcnow`
  default, same order (vastai -> runpod), same `RuntimeError` (verbatim message) if nothing is
  configured, same `Snapshot`. The live collection (GitHub Actions) runs identically.
- **Only deviation, cosmetic**: the `logger.warning` for missing keys is generic
  (`"VASTAI_API_KEY is missing: provider 'vastai' skipped."`) and emitted by the
  `core.ingestion.providers` logger (instead of `core.ingestion.gpu_market`). No test asserts this
  text; it is not a behaviour contract.
- `core/ingestion/__init__.py` (outside the owned module, **not touched**) keeps importing its
  symbols from the shim: the `core.ingestion` facade stays intact.

## 3. Dependencies
No new dependency (`requests` already present in `pyproject.toml`). Nothing to add to the lockfile.

## 4. Downstream -- W2 wave (1 instance = 1 venue)
The foundation is ready. Adding a venue = **3 steps** (documented in
`core/ingestion/providers/__init__.py`):
1. `core/ingestion/providers/<venue>.py`: `parse_<venue>` (pure) + `fetch_<venue>` (token-gated I/O) +
   a `<Venue>Provider` class (`name`, `required_env`, `fetch(now)`), reusing `base.normalize_gpu_model`.
2. Add `<Venue>Provider()` to the `PROVIDERS` tuple.
3. Parity test under `tests/` + (convergence) key in **GitHub Secrets** for the always-on collector.

Each W2 venue writes into its own file -> zero merge collisions.

---

# W2 -- providers_connectors - convergence handoffs

> This batch writes **only** into `core/ingestion/providers/`: 5 venue modules
> (`primeintellect, datacrunch, cudo, hyperstack, tensordock`), the `__init__.py` registry
> (`PROVIDERS` tuple -> **7 venues**), and `tests/` (conftest + `test_parsers_w2.py` +
> `test_registry.py`). Nothing outside the module is touched. Vast/RunPod, the
> `fetch_live_gpu_prices` shim and the collector are **unchanged** (non-regression green).

## W2.0 -- Live validation POSTPONED (worktree without `.env`)
The `lab-W2` worktree has **no** `.env` (keys missing) -> hitting the APIs here is impossible. The
schemas were **reconstructed from the public documentation** (see below) and the parsers tested on
**realistic samples** (unit tests + ruff + mypy green, without a key).
**To do at convergence** (where the Secrets exist):
- run `python -m infra.collectors.gpu_price_snapshot` -> check that the active venues really
  collect;
- for each venue with less than high confidence, **confirm live** the price endpoint and the
  response shape, then adjust the parser if needed (the test contract freezes the sample).

## W2.1 -- Confidence level + points to confirm live
| Venue | Auth | Price endpoint | Confidence | To confirm live |
|---|---|---|---|---|
| **primeintellect** | Bearer `PRIMEINTELLECT_API_KEY` | `GET /api/v1/availability` | **high** (verbatim schema) | is `prices.onDemand` **per offer** (divided by `gpuCount`, the assumption taken) or already per GPU? |
| **datacrunch** | OAuth2 `CLIENT_ID`/`CLIENT_SECRET` | `GET /v1/instance-types` | **high** (stable SDK fields) | shape of `/v1/instance-availability` to enrich the **region** |
| **cudo** | Bearer `CUDO_API_KEY` | `GET /v1/vms/machine-types` | medium | exact endpoint + `{machineTypes:[...]}` envelope + `gpuPriceHr.value` (string); per-data-center variant |
| **hyperstack** | `api_key` header | `GET /v1/core/flavors` | medium | `price_per_hour` **per flavor** (divided by `gpu_count`, assumption) vs already per GPU; meaning of `stock_available`; warning: `.env.example` notes a **401** (regenerate the key) |
| **tensordock** | Bearer `TENSORDOCK_API_KEY` | `GET /api/v2/hostnodes` | lower | v2 envelope **list or mapping/id** (the `_hostnodes_records` helper tolerates both) + exact location of `specs.gpu.price`. Bearer = `TENSORDOCK_API_KEY`, **not** `API_AUTHORIZATION` |

## W2.2 -- RICH fields available per venue (capturing them = future edge)
The current `Snapshot` is minimal (`price, gpu_model, lease_type, availability`). The venues expose
much more -- **captured and documented here**, not emitted yet (schema to enrich, see W2.3):

| Venue | region / DC | GPU memory | vCPU | RAM | disk | spot | provider detail |
|---|---|---|---|---|---|---|---|
| primeintellect | `region`,`dataCenter`,`country` | `gpuMemory` | `vcpu.defaultCount` | `memory.defaultCount` | `disk` | **emitted** (`isSpot`) | **emitted** via `source=primeintellect:<provider>` |
| datacrunch | via `/instance-availability` | `gpu_memory.size_in_gigabytes` | `cpu.number_of_cores` | `memory.size_in_gigabytes` | `storage.size_in_gigabytes` | **emitted** (`spot_price_per_hour`) | -- |
| cudo | `dataCenterId` | `gpuMemoryGib` | (`vcpuPriceHr`) | (`memoryGibPriceHr`) | -- | -- | -- |
| hyperstack | `region_name` | -- | `cpu` | `ram` | `disk` | -- (`/stocks` for fine-grained availability) | -- |
| tensordock | `location.{country,region,city}` | `vram` | `cpu.amount` | `ram.amount` | `storage.amount` | -- | -- |

## W2.3 -- Schema enrichment proposal (protected zone, **not applied**)
To exploit the rich data, add **optional** fields (backward compatible) to
`core.ingestion.protocols.Snapshot` **and** `core.storage.schema`:
`region: str | None`, `gpu_memory_gb: int | None`, `vcpu: int | None`, `ram_gb: int | None`,
`disk_gb: int | None`, `provider_detail: str | None` (sub-provider of an aggregator, as an
alternative to the `source` prefix). Each parser would then fill the columns of table W2.2.
To be carried by the convergence session (touches `core/ingestion/protocols.py` + `core/storage/`).

## W2.4 -- Prime Intellect aggregator deduplication
Prime Intellect aggregates **several underlying providers** -> `source` is qualified
`primeintellect:<provider>` to avoid hiding a venue wired in directly. **Risk**: double counting at
the index level (e.g. `primeintellect:datacrunch` overlaps the direct `datacrunch` venue).
**Convergence recommendation**: a **direct > aggregator** preference strategy (or targeted
exclusion in `build_spot_index`), tracked by `source`.

## W2.5 -- Secrets & CI
- **GitHub Secrets** (always-on collector): add `PRIMEINTELLECT_API_KEY`,
  `DATACRUNCH_CLIENT_ID`, `DATACRUNCH_CLIENT_SECRET`, `CUDO_API_KEY`, `HYPERSTACK_API_KEY`,
  `TENSORDOCK_API_KEY` (already listed in `.env.example`). As soon as a key is set, the key-gated
  registry picks the venue up **automatically** (no other layer changes).
- **CI / `testpaths`**: the W2 tests live in `core/ingestion/providers/tests` -- the **same
  directory as W1** -> the W1 CI note (section 1) already covers adding this directory to the
  isolation loop; **no new path** to declare (`test_parsers_w2.py` + the conftest/registry additions
  are picked up with the directory).

## W2.6 -- Local check (this worktree, green)
```bash
uv run pytest -q core/ingestion/providers/tests                 # 21 passed
uv run pytest -q projects/04_compute_index_curve/tests/test_gpu_market.py  # 4 (non-regression)
uv run pytest -q core/storage/tests/test_collector_rewire.py    # 2 (collector intact)
uv run ruff check . && uv run mypy core                         # green (106 files)
```
