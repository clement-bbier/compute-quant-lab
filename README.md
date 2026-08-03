# Compute Quant Lab

[![CI](https://github.com/clement-bbier/compute-quant-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/clement-bbier/compute-quant-lab/actions/workflows/ci.yml)

A quant research lab that treats **compute** (GPU rental) as an asset class and arbitrages it against its raw material, **electricity**.

## The thesis

Renting a GPU and burning the electricity to power it are two legs of the same trade. The **digital spark spread** is the margin between them: compute revenue (€ or $ per GPU-hour, set by marketplaces like Vast.ai or RunPod) minus the energy cost of producing that GPU-hour (spot electricity price × power draw × PUE). When the spread is structurally wide, compute is cheap relative to its input cost; when it compresses or inverts, compute is expensive relative to the electricity that makes it possible. The lab's projects build the pricing, features, and backtest infrastructure to measure that spread point-in-time and test whether it is tradable.

## Architecture

```mermaid
flowchart LR
    A[Ingestion<br/>ENTSO-E · ERCOT · GPU venues] --> B[Storage<br/>Parquet cold store, point-in-time]
    B --> C[Pricing & Features<br/>spark spread, PUE, exogenous signals]
    C --> D[Backtest & Risk<br/>Rust kernel + Python oracle]
    D --> E[Projects P01-P14<br/>signals, portfolio, dashboards]
```

## Quickstart

**Prerequisites**

| OS | Requirements |
|---|---|
| Windows | [uv](https://docs.astral.sh/uv/), [rustup](https://rustup.rs/) + Visual Studio Build Tools (MSVC C++ workload), `make` (Git Bash provides it) |
| Linux | [uv](https://docs.astral.sh/uv/), [rustup](https://rustup.rs/), `build-essential`, `make` |

Three Rust extension modules (pricing kernel, backtest loop, forward engine) are compiled locally via `maturin` — there's no prebuilt wheel, so a working Rust + C toolchain is required.

```bash
git clone https://github.com/clement-bbier/compute-quant-lab.git
cd compute-quant-lab
make sync    # uv sync --extra dev + builds the 3 Rust kernels
make test    # runs every test suite in isolation (22+ suites)
make demo    # launches the GPU spot benchmark dashboard (Streamlit)
```

If the kernels are missing or out of date (e.g. after a bare `uv sync`, which removes them), `make test` fails fast with a clear message and the fix:

```
kernels missing — run `make kernels`
```

Every Python code path also has a pure-Python fallback (`PythonOracle`), bit-for-bit tested against the Rust kernel — the lab never *requires* Rust to produce correct numbers, only to produce them fast. That claim is measured, not assumed (`scripts/bench_kernels.py`, release build, n=100k): the row-by-row **backtest loop is ~800-1000x faster** in Rust (the case a Python `for` loop is genuinely bad at), the Monte Carlo **forward engine ~2x faster**, but the already-vectorized **pricing kernel is ~5-8x *slower*** in Rust at this size — PyO3/FFI crossing overhead exceeds what a single-pass NumPy/BLAS computation costs. Rust is not a blanket win; it wins where the Python path is an explicit loop.

## Data honesty

Every project defaults to **synthetic data**, and says so explicitly in its results. This is a methodological choice, not a placeholder: it lets the pipeline (point-in-time correctness, look-ahead guards, cost modeling, MLflow reproducibility) be validated and adversarially reviewed *before* any claim of edge is made on real markets. The line between "infrastructure validated" and "alpha claimed" is preregistered — see the signed [L0 ERCOT preregistration](docs/superpowers/specs/2026-06-23-L0-ercot-grid-stress-preregistration.md), frozen before the corresponding analysis ran, as the anti-p-hacking contract.

One branch runs on real data today via a **committed cold store** — no key required on a fresh clone:

- **ENTSO-E FR/DE day-ahead prices** ([`infra/collectors/entsoe_backfill.py`](infra/collectors/entsoe_backfill.py) → [`data/cold/energy/`](data/cold/energy/), 2024-01-01 to today, 89,246 rows, ~1.4 MB), consumed by [P02](projects/02_spread_mean_reversion/) and [P05](projects/05_energy_compute_basis/). `publish_time` is an **approximated convention** (`entsoe-py` returns no publication timestamp): day-ahead auctions clear D-1 ~12:45 Europe/Paris, so `publish_time` is derived from `interval_start` rather than read from the API — documented in [`core/storage/energy_store.py`](core/storage/energy_store.py) and the backfill script's docstring. `ENTSOE_API_TOKEN` becomes optional, used only to refresh beyond the committed range.

**ERCOT** (Texas grid, ~670 LOC across [`core/ingestion/energy/ercot.py`](core/ingestion/energy/ercot.py) and [`ercot_transport.py`](core/ingestion/energy/ercot_transport.py)) is a complete, tested pipeline for grid-stress prediction ([P07](projects/07_exogenous_macro_signal/)) — 14 dedicated tests pass on fixtures — but it is **not yet calibrated on real data**: `data/cold/` contains only `energy/` (ENTSO-E), no committed ERCOT cold store. `run_ercot_calibration.py` requires a real backfill first (`infra/collectors/ercot_backfill.py --start ... --end ...`, needs `GRIDSTATUS_API_KEY`); no calibration result is claimed until that backfill exists. See [P07's own CLAUDE.md](projects/07_exogenous_macro_signal/CLAUDE.md#ercot-branch-l0-grid-stress-real-data) for detail.

The GPU marketplaces (compute leg) are coded and live-validated per venue but not yet cold-stored — real history only accumulates from when the collector first ran (`data/snapshots/`, day by day; no retroactive data exists). See [Live data](#live-data-optional) below for the remaining token-gated sources. The roadmap to fully real, continuously accumulated history is in [`docs/storage-roadmap.md`](docs/storage-roadmap.md).

## Live data (optional)

None of this is required for `make test` or CI — everything above runs on synthetic fixtures with zero network calls. Live data is opt-in, for anyone who wants to point the lab at real markets.

```bash
cp .env.example .env   # never commit .env
```

| Variable | Unlocks | Where to get it |
|---|---|---|
| `ENTSOE_API_TOKEN` | Live-refresh of FR/DE electricity spot price beyond the committed cold store (optional — see [Data honesty](#data-honesty)) | ENTSO-E Transparency Platform |
| `GRIDSTATUS_API_KEY` | ERCOT real-time market via a hosted API (bypasses the geoblock on ercot.com outside the US) | GridStatus.io |
| `VASTAI_API_KEY` | Vast.ai GPU marketplace connector | Vast.ai console |
| `RUNPOD_API_KEY` | RunPod GPU marketplace connector | RunPod console |
| `PRIMEINTELLECT_API_KEY` | Prime Intellect GPU marketplace connector | Prime Intellect console |
| `DATACRUNCH_CLIENT_ID` / `DATACRUNCH_CLIENT_SECRET` | DataCrunch GPU marketplace connector | DataCrunch console |
| `CUDO_API_KEY` | Cudo Compute GPU marketplace connector | Cudo Compute console |
| `HYPERSTACK_API_KEY` | Hyperstack GPU marketplace connector | Hyperstack console |
| `TENSORDOCK_API_KEY` | TensorDock GPU marketplace connector (dormant venue: live hostnode inventory has been empty on every check to date) | TensorDock console |
| `LAMBDA_API_KEY` | Lambda Cloud GPU marketplace (connector not yet built) | Lambda Cloud console |
| `CRUSOE_ACCESS_KEY_ID` / `CRUSOE_SECRET_KEY` | Crusoe Cloud GPU marketplace (connector not yet built) | Crusoe Cloud console |
| `GENESISCLOUD_API_KEY` | Genesis Cloud GPU marketplace (connector not yet built) | Genesis Cloud console |
| `SILICONDATA_API_TOKEN` | Canonical compute spot index (paid reference feed) | Silicon Data |

Live-dependent tests are marked `-m live` and are opt-in only (`uv run pytest -m live`); the default `make test` / CI never requires a key. The GitHub Actions collector ([`.github/workflows/collect.yml`](.github/workflows/collect.yml)) that accumulates GPU price history day over day reads these same variable names from repository secrets — no values live in this repo.

## Projects index

| Project | Question | Data |
|---|---|---|
| [P01 — Digital Spark Spread](projects/01_digital_spark_spread/) | What's the point-in-time margin between compute revenue and energy cost? | Synthetic |
| [P02 — Spread Mean Reversion](projects/02_spread_mean_reversion/) | Does the energy↔compute spread mean-revert tradably? | Real (ENTSO-E cold store + marketplace snapshots) |
| [P03 — GPU Vol & Term Structure](projects/03_gpu_vol_term_structure/) | Does the compute forward curve's shape (contango/backwardation) carry a signal? | Synthetic |
| [P04 — Compute Index & Curve](projects/04_compute_index_curve/) | What's a defensible spot index and simulated forward curve for compute? | Synthetic (real spot feeding in) |
| [P05 — Energy↔Compute Basis](projects/05_energy_compute_basis/) | How does the spread differ across regions (FR vs. DE), and why? | Real energy (ENTSO-E cold store); compute real if snapshots accumulated |
| [P06 — Compute Futures Pricing](projects/06_compute_futures_pricing/) | What would compute futures (unlisted) be worth theoretically? | Synthetic |
| [P07 — Exogenous Macro Signal](projects/07_exogenous_macro_signal/) | Do gas price / weather lead the energy leg? | ERCOT branch: real pipeline, tested on fixtures, not yet calibrated (no committed cold store); rest synthetic |
| [P08 — Backtest & Risk Engine](projects/08_backtest_risk_engine/) | Can every strategy plug into one point-in-time, cost-aware backtest engine? | Synthetic |
| [P09 — ML Signal Ensemble](projects/09_ml_signal_ensemble/) | Does an XGBoost ensemble find directional edge without overfitting? | Synthetic |
| [P10 — Portfolio & Execution](projects/10_portfolio_execution/) | Does the desk survive once real signals meet real execution costs? | Synthetic |
| P11 — Storage Layer ([`core/storage/`](core/storage/)) | What's the versioned, point-in-time cold store every project reads from? | N/A (infra) |
| P12 — Signal Promotion ([`core/signals/`](core/signals/)) | How do P02/P06/P09 signals get promoted into one production interface? | N/A (infra) |
| [P13 — Compute Benchmark](projects/13_compute_benchmark/) | What's a publishable, auditable reference price for a GPU-hour? | Real |
| [P14 — Service Product](projects/14_service/) | Can the benchmark become a product (free measurement / paid timing)? | Real |

## Results

All figures below are reproducible by rerunning the cited command; where the artifact itself is committed, the table links straight to it (coverage output is regenerated fresh each run — see the `.gitignore` — and instead uploaded as a CI artifact on every push).

| Metric | Value | Source |
|---|---|---|
| Test suites | 23 (fails below 20) | `make test` output / [Makefile](Makefile) |
| Test count | 663 passed, 15 skipped (live-only) | `make test` output |
| Source coverage (core+projects+infra, excluding tests) | 93% (4,511 statements) | `make coverage` (also uploaded as the `coverage-xml` artifact on [CI](https://github.com/clement-bbier/compute-quant-lab/actions/workflows/ci.yml)) |
| P01 mean spread | 2.024 EUR/GPU·h | [`projects/01_digital_spark_spread/results/run_summary.json`](projects/01_digital_spark_spread/results/run_summary.json) |
| P02 backtest Sharpe (real data, annualized √35040) | 5.96, t-stat 1.69 (n=2,807 grid) / 0.67 (n=441 compute-effective), 95% CI spans zero at both — **not distinguishable from zero** | [`projects/02_spread_mean_reversion/results/SYNTHESIS.md`](projects/02_spread_mean_reversion/results/SYNTHESIS.md) |
| P02 backtest Sharpe (prior simulated reference, flagged non-credible) | 7.70 | [`projects/02_spread_mean_reversion/results/SYNTHESIS.md`](projects/02_spread_mean_reversion/results/SYNTHESIS.md) |
| P08 engine demo Sharpe | 0.615 | [`projects/08_backtest_risk_engine/results/SYNTHESIS.md`](projects/08_backtest_risk_engine/results/SYNTHESIS.md) |
| P09 ensemble Sharpe / PSR | 0.17 / 0.66, t-stat 0.42 (n=2,190), 95% CI [−0.63, 0.97] — spans zero | [`projects/09_ml_signal_ensemble/results/SYNTHESIS.md`](projects/09_ml_signal_ensemble/results/SYNTHESIS.md) |
| P10 desk net Sharpe (real signals, after costs) | −7.12, t-stat −16.55 (n=1,500), 95% CI [−7.96, −6.28] — decisively negative, not just noisy | [`projects/10_portfolio_execution/results/SYNTHESIS.md`](projects/10_portfolio_execution/results/SYNTHESIS.md) |
| P11 storage layer tests | 40 passed | [`core/storage/results/SYNTHESIS.md`](core/storage/results/SYNTHESIS.md) |
| P13 published models | 24 (A100, A40, A6000, B200, B300, CPUNODE, H100, H200, L4, L40, L40S, RTX3080, RTX3090, RTX4000ADA, RTX4090, RTX5080, RTX5090, RTX6000ADA, RTX6000ADA48GB, RTXPRO4000, RTXPRO4500, RTXPRO5000, RTXPRO6000B96GB, V100) across 15 venues | [`projects/13_compute_benchmark/results/benchmark_summary.md`](projects/13_compute_benchmark/results/benchmark_summary.md) |

The negative and near-zero Sharpes above are reported deliberately, with their statistical uncertainty printed alongside the point estimate: [`/backtest-pitfalls`](.claude/skills/backtest-pitfalls/) auditing exists precisely to stop a flattering-but-fragile number from being presented as edge (see P02's own adversarial verdict on both its real 5.96 — not distinguishable from zero at this sample size — and its prior simulated 7.70, non-credible by construction; neither is a validated result, for different reasons).

## Screenshots

| Screenshot | Launch command | View captured |
|---|---|---|
| ![P13 compute benchmark dashboard](docs/assets/p13-benchmark-dashboard.png) | `uv run streamlit run projects/13_compute_benchmark/dashboard/app.py` | Index curve + cross-venue dispersion cloud, at least one model with 2+ venues |
| ![P14 service product dashboard](docs/assets/p14-service-dashboard.png) | `uv run streamlit run projects/14_service/dashboard/app.py` | "Cheapest GPU right now" view with the free-tier heuristic recommendation visible |

## Roadmap

- Storage: cold-store phases 0-1 are done ([P11](core/storage/)); real-time serving (hot store, streaming) is phases 2-4, documented but not built — see [`docs/storage-roadmap.md`](docs/storage-roadmap.md).
- Energy leg: **done** — FR/DE ENTSO-E day-ahead prices are committed to a cold store ([`data/cold/energy/`](data/cold/energy/)) and read by P02/P05 with zero key required; `ENTSOE_API_TOKEN` only refreshes beyond the committed range.
- Compute leg: still the shallow side — real marketplace history only accumulates from when `infra/collectors/gpu_price_snapshot.py` first ran (~1 month so far), with no cold store or retroactive backfill yet (unlike energy, GPU marketplace spot prices have no historical API to backfill from).
- ERCOT (P07 grid-stress branch): pipeline complete and tested on fixtures, but not calibrated — needs a real backfill (`infra/collectors/ercot_backfill.py`, `GRIDSTATUS_API_KEY`) before any result can be claimed.
- Parked items and known gaps: [`docs/BACKLOG.md`](docs/BACKLOG.md).

## License

[MIT](LICENSE)
