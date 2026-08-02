# Project 14 — `service_product`: the revenue vehicle

> LOCAL context. Global glossary and conventions: root `CLAUDE.md`.
> Instance framing: `docs/orchestration/instances/WS_service_product.md`.

## Thesis

Turn the asset (multi-venue benchmark + procurement signal) into a **product people pay
for**: a dashboard / alerting system for "**the cheapest GPU right now
+ price trend**". **Public free tier** = the *measurement*. **Premium** = the *decision*
(calibrated timing), plugged into the **private edge** — never exposed in the clear.

## Public / edge boundary (rule #1)

| Layer | What | Where |
|---|---|---|
| **Measurement** (PUBLIC) | who is cheapest, at what level, what trend | this module |
| **Decision** (PREMIUM/edge) | when to rent / on which venue, calibrated params | `private/` (WP), **never committed** |

The product depends only on a **Protocol** (`SignalSource`): the default public
implementation is a **trivial non-edge heuristic**; the private edge **substitutes it
locally**. Since nothing edge-specific is ever imported, edge leakage is
*structurally* impossible (guarded by `mypy` + an anti-import test).

## Architecture (`src/`)

- **`views.py`** — the *measurement*. Reads the cold store (`core.storage`, injected via the
  `SnapshotStore` Protocol) and produces a point-in-time `MarketView` (retained venues sorted +
  canonical index) and a `price_curve`. Index & anti look-ahead **delegated** to
  `core.ingestion.build_spot_index` (reuse, zero rewrite of `core/`).
- **`signal_iface.py`** — the *boundary*. `Action`, `ProcurementSignal`, `SignalProvenance`
  (**mandatory** `simulated` flag), the **`SignalSource`** Protocol (single injection
  point) and `NaiveSignalSource` (public impl: `RENT_NOW` iff the cheapest venue is below the
  cross-venue median; otherwise `WAIT`).
- **`alerts.py`** — the *alert skeleton*. `AlertEngine(source, notifier)` evaluates
  declarative rules (`PriceBelow` = pure public; `ActionIs` = driven by the injected
  edge). `Notifier` = stub (in-memory / log); real delivery (email/webhook) is
  out of scope for the PoC. Deterministic and point-in-time (`fired_at = market.as_of`).

## Dashboard (`dashboard/app.py`)

Streamlit showcase (pure I/O layer): cheapest venue right now, cross-venue dispersion,
trend curve, free heuristic recommendation (labeled non-edge), methodology section.
Degrades gracefully when history is thin.

```bash
streamlit run projects/14_service/dashboard/app.py
```

## Data

Everything comes from the **versioned cold store** (`core.storage`, Parquet lake). Compute
history exists nowhere else: it accumulates continuously (24/7 collector). At startup the
lake can be thin — the product handles it (degradation messages), no invented value.

## Tests (`tests/`) — tests-first

| File | Guarantee |
|---|---|
| `test_views.py` | cheapest *retained* venue + canonical index on fixture |
| `test_signal_iface.py` | naive `RENT_NOW`/`WAIT` recommendation; mandatory `simulated` provenance |
| `test_alerts.py` | triggers at the right threshold (mocked signal); stub notifier |
| `test_point_in_time.py` | **anti look-ahead** (a future observation does not enter a past measurement) |
| `test_di_without_edge.py` | the product runs **without** edge; edge is substitutable; no `private` import |

```bash
uv run pytest projects/14_service/tests
```

## Status (PoC-now)

- [x] Public measurement (`views`) on the real cold store, point-in-time, reuses `build_spot_index`
- [x] `SignalSource` boundary + default naive public impl (non-edge, `simulated=True`)
- [x] Alert skeleton (single injection point, declarative rules, stub notifier)
- [x] Streamlit dashboard (cheapest + dispersion + trend + methodology, graceful degradation)
- [x] 36 tests passing; no edge in the clear
- [ ] **Convergence handoff**: add `projects/14_service/tests` to `testpaths` (protected zone)
- [ ] *Institutional-target*: auth/subscriptions, monetized API, deployment, premium wired to the edge (WP)

## Dependencies

Upstream: P11 (`core.storage`), P04 (`core.ingestion.build_spot_index`), W1/W2 (venues), ideally
WD (`projects/13`) once merged (otherwise a minimal view from the lake — current case). At build time: only needs
the cold store + a `SignalSource` (naive by default). **Rust-free**: the product does
not pull in the backtest engine.
