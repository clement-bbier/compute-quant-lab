"""P13 showcase layer — public compute spot benchmark (index + dispersion).

Consumes **only** the foundation (`core.storage` to read the cold store,
`core.ingestion.build_spot_index` for canonical aggregation). No rewriting of
``core``: consumption only. Pure computation logic here; I/O (lake reads,
dashboard, MLflow) lives in ``run_build_benchmark.py`` and ``dashboard/app.py``.

Edge boundary (PUBLIC showcase): we publish the **measurement** (daily reference price
+ descriptive cross-venue dispersion), never the timing **decision** ("rent on X
now"). Cf. ``projects/13_compute_benchmark/CLAUDE.md`` §edge boundary.
"""
