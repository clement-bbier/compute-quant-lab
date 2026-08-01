"""Streamlit **demo** dashboard for the compute spot benchmark (reads the real cold store).

Renders the publishable **measurement**: canonical index curve + cross-venue dispersion
(cloud of venues around the index, spread %, named average levels). No
timing recommendation ("rent on X now") — that's the edge boundary.

Run: ``uv run streamlit run projects/13_compute_benchmark/dashboard/app.py``.
``data/snapshots`` is versioned as plain git on ``main``. For the most recent
collection (accumulated continuously by the CI cron), enter in the sidebar the root
of a cold store populated via ``git checkout data-snapshots -- data/snapshots``.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Makes the project package `benchmark` (under src/) importable.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from benchmark.dispersion import venue_levels, venue_rates_at  # noqa: E402
from benchmark.index_series import (  # noqa: E402
    build_index_series,
    daily_fix_grid,
    observed_fix_grid,
)
from benchmark.report import multi_venue_models, summarize_history  # noqa: E402
from core.ingestion.compute_index import DEFAULT_INDEX_CONFIG  # noqa: E402
from core.ingestion.protocols import Snapshot  # noqa: E402
from core.storage import ParquetSnapshotStore  # noqa: E402
from core.utils.config import SNAPSHOTS_DIR  # noqa: E402
from dashboard_kit import COLORS, SIZES, apply_page, header, money_axis  # noqa: E402

CONFIG = DEFAULT_INDEX_CONFIG


@st.cache_data(show_spinner=False)
def _load(root: str) -> list[Snapshot]:
    """Load snapshots from the cold store (cached by root)."""
    return ParquetSnapshotStore(root).load()


def _grid(snapshots: list[Snapshot], model: str, cadence: str) -> list[dt.datetime]:
    """Fix grid based on the chosen cadence (canonical daily vs. per-snapshot demo)."""
    history = summarize_history(snapshots)
    if cadence.startswith("Daily"):
        if history.first_at is None or history.last_at is None:
            return []
        return daily_fix_grid(history.first_at, history.last_at + CONFIG.staleness)
    return observed_fix_grid(snapshots, gpu_model=model)


def _venue_points(snapshots: list[Snapshot], grid: list[dt.datetime], model: str) -> pd.DataFrame:
    """Per-venue rates retained at each fix (dispersion cloud around the index)."""
    rows = []
    for as_of in grid:
        for r in CONFIG.outlier_filter.filter(
            venue_rates_at(snapshots, as_of, model, config=CONFIG)
        ):
            rows.append({"as_of": as_of, "source": r.source, "rate": r.rate})
    return pd.DataFrame(rows)


def main() -> None:
    template = apply_page(title="Compute Spot Benchmark", icon="⚡")
    header(
        "Compute Spot Benchmark",
        "Real multi-venue GPU-hour reference price · point-in-time (UTC) · "
        'measurement only, no timing signal ("rent on X now").',
    )

    root = st.sidebar.text_input("Cold store root (Parquet)", value=str(SNAPSHOTS_DIR))
    snapshots = _load(root)

    history = summarize_history(snapshots)
    if not snapshots:
        st.warning(
            "Cold store empty. Populate the lake then enter its root:\n\n"
            "`git checkout data-snapshots -- data/snapshots`."
        )
        return

    kpi = st.columns(4)
    kpi[0].metric("Readings", f"{history.n_snapshots:,}")
    kpi[1].metric("Venues", str(history.n_venues), help=", ".join(history.sources))
    kpi[2].metric("Distinct instants", f"{history.n_distinct_timestamps:,}")
    kpi[3].metric("History span", f"{history.span_hours / 24:.1f} d")

    candidates = multi_venue_models(snapshots) or sorted({s.gpu_model for s in snapshots})
    col_model, col_cad = st.sidebar, st.sidebar
    model = col_model.selectbox("GPU model", candidates)
    cadence = col_cad.radio(
        "Cadence",
        ["Daily (canonical, settlement)", "Demo (per observed snapshot)"],
        help="The published product = daily fix; the demo cadence shows every observed instant.",
    )

    grid = _grid(snapshots, model, cadence)
    series = build_index_series(snapshots, grid, model, config=CONFIG)
    index_df = series.to_frame()
    venue_df = _venue_points(snapshots, grid, model)

    left, right = st.columns(2)
    with left:
        st.subheader(f"Canonical index — {model}")
        fig = go.Figure()
        if not venue_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=venue_df["as_of"],
                    y=venue_df["rate"],
                    mode="markers",
                    marker=dict(size=7, opacity=0.5),
                    name="venues (dispersion)",
                    text=venue_df["source"],
                )
            )
        if not index_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=index_df["as_of"],
                    y=index_df["price_usd_per_hour"],
                    mode="lines+markers",
                    line=dict(width=2.5, color=COLORS["accent"]),
                    marker=dict(size=5, color=COLORS["accent"]),
                    name="index",
                )
            )
        fig.update_layout(template=template, xaxis_title="fix (UTC)", height=SIZES["chart_height"])
        money_axis(fig)
        st.plotly_chart(fig, use_container_width=True)
        if series.skipped:
            st.caption(
                f"{len(series.skipped)} fix(es) without a fresh venue (skipped, no carry-forward)."
            )

    with right:
        st.subheader("Average levels per venue (descriptive)")
        levels = venue_levels(snapshots, grid, model, config=CONFIG)
        if levels:
            st.dataframe(
                pd.DataFrame(
                    {
                        "venue": [lv.source for lv in levels],
                        "average level $/h": [round(lv.mean_rate, 4) for lv in levels],
                        "average discount vs. index": [
                            f"{lv.mean_discount_vs_index:+.1%}" for lv in levels
                        ],
                        "fixes": [lv.n_fixes for lv in levels],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                'Descriptive measurement over the window — **not** a "rent on X now" signal.'
            )
        else:
            st.write("Not enough history for per-venue levels.")


if __name__ == "__main__":
    main()
