# `gpu-price` MCP server

Exposes the **real** history of GPU rental prices (snapshots accumulated in `data/snapshots/`)
via MCP (stdio). Read-only, point-in-time.

| Attribute | Value |
| --- | --- |
| Unit | USD per GPU-hour ($/GPU-h) |
| Timezone | UTC, tz-aware (naive instants rejected) |
| Frequency | scheduled snapshot (collector `infra/collectors/gpu_price_snapshot.py`) |
| Sources | marketplaces (`source`: vastai, runpod, …) |
| Real/simulated | **real** (observed spot) |
| Backend | Parquet lake `core.storage.ParquetPriceStore` under `data/snapshots/` |

## Tools

- `list_gpu_models(as_of?)` — known models (sorted, bounded point-in-time).
- `latest_price(gpu_model, lease_type="on_demand", as_of?)` — latest price per source + summary.
- `price_history(gpu_model, start?, as_of?, source?, lease_type?)` — time series.
- `summary_stats(gpu_model, lease_type?, as_of?)` — count/min/max/mean/median/std, overall and per source.
- `query(sql)` — **raw** DuckDB SQL against the `prices` view.

## Warning: Security

`query` reuses `core.storage.query`: **the full power of DuckDB** (`read_csv`, `COPY … TO`,
`INSTALL httpfs`) remains accessible. Driven by an LLM, this server can be hijacked via
prompt injection (file writes/exfiltration). **Only expose it to trusted agents, on a local
machine.** There is no point-in-time guard on `query` (raw lake access).
