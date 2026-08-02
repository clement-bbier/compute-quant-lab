# Compute Spot Benchmark — run summary

**Real** spot index (provenance `real_spot`), point-in-time, UTC. Published measurement:
GPU-hour reference price (canonical daily fix at 00:30 UTC) + descriptive
cross-venue dispersion. **No timing signal** ("rent on X now") published.

## History state (honest — thin at the start, it grows)
- Readings: **85935** · venues: **15** (cudo, datacrunch, hyperstack, primeintellect:crusoecloud, primeintellect:datacrunch, primeintellect:dc_gnu, primeintellect:dc_wildebeest, primeintellect:lambdalabs, primeintellect:massedcompute, primeintellect:nebius, primeintellect:primecompute, primeintellect:runpod, primeintellect:vultr, runpod, vastai)
- Distinct instants: **441** · span: **701.7 h**
- Window: 2026-06-22 12:56:58.007071+00:00 → 2026-07-21 18:41:45.595446+00:00
- Daily fixes computed on the grid: **30**

## Aggregate
- Published models: **24** (A100, A40, A6000, B200, B300, CPUNODE, H100, H200, L4, L40, L40S, RTX3080, RTX3090, RTX4000ADA, RTX4090, RTX5080, RTX5090, RTX6000ADA, RTX6000ADA48GB, RTXPRO4000, RTXPRO4500, RTXPRO5000, RTXPRO6000B96GB, V100)
- Mean cross-venue spread % (defined fixes): **63.39%**

## Latest fix per model

| Model | Index $/GPU·h | Venues | Spread % | Cheapest |
|---|---|---|---|---|
| A100 | 1.4640 | 8 | 54.64% | runpod |
| A40 | 0.2050 | 3 | 142.83% | hyperstack |
| A6000 | 0.5500 | 4 | 20.00% | hyperstack |
| B200 | 6.0000 | 3 | 3.67% | runpod |
| B300 | 6.9400 | 1 | n/a (single venue) | — |
| CPUNODE | 0.0779 | 2 | 56.74% | primeintellect:datacrunch |
| H100 | 2.5133 | 7 | 93.50% | cudo |
| H200 | 3.0063 | 4 | 16.96% | hyperstack |
| L4 | 0.2039 | 2 | 182.56% | vastai |
| L40 | 0.8500 | 3 | 36.47% | runpod |
| L40S | 0.8700 | 6 | 66.67% | runpod |
| RTX3080 | 0.1700 | 1 | n/a (single venue) | — |
| RTX3090 | 0.1711 | 2 | 57.14% | vastai |
| RTX4000ADA | 0.2000 | 1 | n/a (single venue) | — |
| RTX4090 | 0.2458 | 2 | 76.61% | vastai |
| RTX5080 | 0.2854 | 2 | 73.33% | vastai |
| RTX5090 | 0.5791 | 3 | 90.60% | vastai |
| RTX6000ADA | 0.7400 | 1 | n/a (single venue) | — |
| RTX6000ADA48GB | 0.7500 | 1 | n/a (single venue) | — |
| RTXPRO4000 | 0.5000 | 1 | n/a (single venue) | — |
| RTXPRO4500 | 0.3400 | 1 | n/a (single venue) | — |
| RTXPRO5000 | 0.7526 | 2 | 17.91% | vastai |
| RTXPRO6000B96GB | 1.8450 | 2 | 4.88% | primeintellect:massedcompute |
| V100 | 0.1900 | 3 | 21.05% | datacrunch |

## Average levels per venue (descriptive, window — NOT a timing signal)

| Model | Venue | Average level $/h | Average discount vs. index |
|---|---|---|---|
| A100 | cudo | 1.5000 | +3.12% |
| A100 | datacrunch | 1.5400 | +5.87% |
| A100 | hyperstack | 1.3908 | -4.39% |
| A100 | primeintellect:crusoecloud | 1.6500 | +13.43% |
| A100 | primeintellect:datacrunch | 1.7067 | +17.36% |
| A100 | primeintellect:lambdalabs | 1.9900 | +36.36% |
| A100 | primeintellect:massedcompute | 1.2220 | -15.99% |
| A100 | primeintellect:runpod | 1.4665 | +0.77% |
| A100 | runpod | 1.1937 | -17.89% |
| A40 | hyperstack | 0.1500 | -26.83% |
| A40 | primeintellect:runpod | 0.4355 | +112.44% |
| A40 | runpod | 0.2600 | +26.83% |
| A6000 | datacrunch | 0.6100 | +10.91% |
| A6000 | hyperstack | 0.5000 | -9.09% |
| A6000 | primeintellect:datacrunch | 0.6100 | +10.91% |
| A6000 | primeintellect:massedcompute | 0.5400 | -1.82% |
| A6000 | primeintellect:runpod | 0.5030 | -8.54% |
| B200 | datacrunch | 6.1100 | +7.33% |
| B200 | hyperstack | 5.6875 | -3.33% |
| B200 | primeintellect:datacrunch | 6.1100 | +7.36% |
| B200 | primeintellect:dc_wildebeest | 4.4000 | -6.63% |
| B200 | primeintellect:lambdalabs | 6.6900 | +16.60% |
| B200 | runpod | 5.8900 | +5.74% |
| B200 | vastai | 4.7563 | -10.62% |
| B300 | runpod | 6.9400 | +3.20% |
| B300 | vastai | 5.1165 | -16.01% |
| CPUNODE | primeintellect:crusoecloud | 0.1000 | +9.88% |
| CPUNODE | primeintellect:datacrunch | 0.0581 | -37.35% |
| CPUNODE | primeintellect:dc_wildebeest | 0.7936 | +82.44% |
| CPUNODE | primeintellect:nebius | 0.7936 | +82.44% |
| H100 | cudo | 1.7900 | -25.26% |
| H100 | datacrunch | 3.2500 | +35.70% |
| H100 | hyperstack | 2.4367 | +0.88% |
| H100 | primeintellect:datacrunch | 3.2500 | +35.70% |
| H100 | primeintellect:lambdalabs | 4.0424 | +71.00% |
| H100 | primeintellect:massedcompute | 2.3500 | -1.88% |
| H100 | primeintellect:primecompute | 1.8000 | -24.36% |
| H100 | runpod | 2.5900 | +8.14% |
| H100 | vastai | 1.6049 | -32.28% |
| H200 | datacrunch | 4.0000 | +45.29% |
| H200 | hyperstack | 3.8430 | +39.19% |
| H200 | primeintellect:datacrunch | 4.0000 | +45.29% |
| H200 | primeintellect:dc_wildebeest | 2.9900 | +14.13% |
| H200 | primeintellect:lambdalabs | 2.2900 | -12.65% |
| H200 | primeintellect:nebius | 4.5000 | +63.45% |
| H200 | primeintellect:primecompute | 3.5000 | +15.94% |
| H200 | primeintellect:vultr | 1.9900 | -23.52% |
| H200 | runpod | 2.0450 | -22.00% |
| H200 | vastai | 2.2255 | -17.19% |
| L4 | runpod | 0.3900 | +36.47% |
| L4 | vastai | 0.0336 | -84.17% |
| L40 | hyperstack | 1.0000 | +17.65% |
| L40 | primeintellect:massedcompute | 0.8600 | +1.18% |
| L40 | primeintellect:runpod | 0.8319 | -2.13% |
| L40 | runpod | 0.6900 | -18.82% |
| L40S | cudo | 0.8700 | -3.56% |
| L40S | datacrunch | 1.3700 | +51.68% |
| L40S | primeintellect:crusoecloud | 1.0000 | +11.93% |
| L40S | primeintellect:datacrunch | 1.3700 | +51.64% |
| L40S | primeintellect:massedcompute | 0.8200 | -9.10% |
| L40S | primeintellect:nebius | 1.5500 | +63.06% |
| L40S | primeintellect:runpod | 1.0013 | +10.27% |
| L40S | primeintellect:vultr | 1.6710 | +72.49% |
| L40S | runpod | 0.7900 | -12.43% |
| L40S | vastai | 0.4286 | -55.82% |
| RTX3080 | runpod | 0.1700 | +35.47% |
| RTX3080 | vastai | 0.0289 | -70.95% |
| RTX3090 | runpod | 0.2200 | +7.53% |
| RTX3090 | vastai | 0.1236 | -28.24% |
| RTX4000ADA | runpod | 0.2000 | +1.64% |
| RTX4000ADA | vastai | 0.0681 | -49.17% |
| RTX4090 | primeintellect:runpod | 0.7015 | +187.85% |
| RTX4090 | runpod | 0.3400 | +34.08% |
| RTX4090 | vastai | 0.1665 | -35.26% |
| RTX5080 | runpod | 0.3900 | +14.48% |
| RTX5080 | vastai | 0.1709 | -39.49% |
| RTX5090 | primeintellect:runpod | 1.0007 | +77.87% |
| RTX5090 | runpod | 0.6900 | +23.54% |
| RTX5090 | vastai | 0.4314 | -23.54% |
| RTX6000ADA | runpod | 0.7400 | +10.69% |
| RTX6000ADA | vastai | 0.3242 | -40.09% |
| RTX6000ADA48GB | primeintellect:datacrunch | 1.0400 | +16.20% |
| RTX6000ADA48GB | primeintellect:massedcompute | 0.7500 | -6.26% |
| RTX6000ADA48GB | primeintellect:runpod | 0.7822 | +2.10% |
| RTXPRO4000 | runpod | 0.5000 | +5.37% |
| RTXPRO4000 | vastai | 0.1507 | -53.68% |
| RTXPRO4500 | runpod | 0.3400 | +0.40% |
| RTXPRO4500 | vastai | 0.3267 | -2.01% |
| RTXPRO5000 | runpod | 0.8200 | +12.55% |
| RTXPRO5000 | vastai | 0.6324 | -12.99% |
| RTXPRO6000B96GB | primeintellect:datacrunch | 1.8900 | +2.20% |
| RTXPRO6000B96GB | primeintellect:massedcompute | 1.8000 | -2.44% |
| V100 | datacrunch | 0.1700 | -10.82% |
| V100 | primeintellect:datacrunch | 0.1700 | -11.05% |
| V100 | runpod | 0.2113 | +10.82% |
