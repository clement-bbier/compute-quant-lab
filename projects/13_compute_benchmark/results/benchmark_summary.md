# Compute Spot Benchmark — run summary

**Real** spot index (provenance `real_spot`), point-in-time, UTC. Published measurement:
GPU-hour reference price (canonical daily fix at 00:30 UTC) + descriptive
cross-venue dispersion. **No timing signal** ("rent on X now") published.

## History state (honest — thin at the start, it grows)
- Readings: **250** · venues: **2** (runpod, vastai)
- Distinct instants: **4** · span: **5.7 h**
- Window: 2026-06-22 12:56:58.007071+00:00 → 2026-06-22 18:36:00.036491+00:00
- Daily fixes computed on the grid: **1**

## Aggregate
- Published models: **6** (B200, H100, H200, RTX4090, RTX5090, V100)
- Mean cross-venue spread % (defined fixes): **64.06%**

## Latest fix per model

| Model | Index $/GPU·h | Venues | Spread % | Cheapest |
|---|---|---|---|---|
| B200 | 4.8785 | 2 | 41.47% | vastai |
| H100 | 2.5900 | 1 | n/a (single venue) | — |
| H200 | 1.9930 | 2 | 5.22% | vastai |
| RTX4090 | 0.2544 | 2 | 67.25% | vastai |
| RTX5090 | 0.5742 | 2 | 40.35% | vastai |
| V100 | 0.1148 | 2 | 166.01% | vastai |

## Average levels per venue (descriptive, window — NOT a timing signal)

| Model | Venue | Average level $/h | Average discount vs. index |
|---|---|---|---|
| B200 | runpod | 5.8900 | +20.73% |
| B200 | vastai | 3.8670 | -20.73% |
| H100 | runpod | 2.5900 | +0.00% |
| H200 | runpod | 2.0450 | +2.61% |
| H200 | vastai | 1.9410 | -2.61% |
| RTX4090 | runpod | 0.3400 | +33.62% |
| RTX4090 | vastai | 0.1689 | -33.62% |
| RTX5090 | runpod | 0.6900 | +20.17% |
| RTX5090 | vastai | 0.4583 | -20.17% |
| V100 | runpod | 0.2100 | +83.01% |
| V100 | vastai | 0.0195 | -83.01% |
