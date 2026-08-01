"""Public "cheapest GPU right now" dashboard — the free tier showcase.

Isolated I/O layer (Streamlit): no business logic here, everything is delegated to ``src/``
(``views`` for the measurement, ``signal_iface``/``alerts`` for the recommendation). Reads the
**versioned cold store** (``core.storage``). Degrades gracefully when history is thin.

Edge boundary: only the **measurement** is displayed (who is cheapest, at what level,
what trend) plus a **free heuristic recommendation** explicitly labeled non-edge.
The **calibrated timing** (premium) lives in ``private/`` and never appears here.

Launch: ``streamlit run projects/14_service/dashboard/app.py``.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.ingestion.compute_index import InsufficientDataError
from core.storage import ParquetSnapshotStore
from core.utils.config import SNAPSHOTS_DIR

# Makes the product modules (under src/) importable outside pytest (after stable imports).
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from signal_iface import Action, NaiveSignalSource  # noqa: E402  (after sys.path addition)
from views import MarketView, price_curve, read_market  # noqa: E402

#: Fallback if the lake is still empty (fresh clone) — no model present yet.
_FALLBACK_MODELS: list[str] = ["H100", "H200", "B200"]
#: Depth of the trend curve (days).
CURVE_LOOKBACK_DAYS: int = 30


def _store() -> ParquetSnapshotStore:
    return ParquetSnapshotStore(SNAPSHOTS_DIR)


def _available_models(store: ParquetSnapshotStore) -> list[str]:
    """GPU models actually present in the lake (sorted), fallback if the lake is empty."""
    models = sorted({s.gpu_model for s in store.load()})
    return models or _FALLBACK_MODELS


def _render_cheapest(market: MarketView) -> None:
    cheapest = market.cheapest
    col1, col2, col3 = st.columns(3)
    col1.metric("Cheapest venue", cheapest.source, f"{cheapest.rate:.2f} $/GPU·h")
    col2.metric("Canonical index", f"{market.index_price:.2f} $/GPU·h", help=market.method)
    col3.metric("Venues retained", str(len(market.venues)))

    naive = NaiveSignalSource().assess(market)
    badge = "🟢 RENT NOW" if naive.action is Action.RENT_NOW else "⏸️ WAIT"
    st.info(
        f"**Free recommendation: {badge}** — {naive.rationale}\n\n"
        "_Uncalibrated public heuristic. **Calibrated timing** (when to rent to "
        "minimize cost) is a **premium** service._"
    )


def _render_dispersion(market: MarketView) -> None:
    cheapest_rate = market.cheapest.rate
    rows = [
        {
            "venue": v.source,
            "$/GPU·h": round(v.rate, 4),
            "gap vs cheapest": f"+{(v.rate / cheapest_rate - 1) * 100:.1f} %",
            "availability (GPU)": v.availability,
        }
        for v in market.venues
    ]
    st.subheader("Cross-venue dispersion")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_curve(store: ParquetSnapshotStore, model: str) -> None:
    now = pd.Timestamp.now(tz="UTC")
    timestamps = list(pd.date_range(end=now, periods=CURVE_LOOKBACK_DAYS, freq="D").to_pydatetime())
    curve = price_curve(store, model, timestamps)
    if curve["index_price"].isna().all():
        st.caption("Not enough history yet to plot the trend.")
        return
    fig = go.Figure(go.Scatter(x=curve["as_of"], y=curve["index_price"], mode="lines+markers"))
    fig.update_layout(
        title=f"{model} spot index — last {CURVE_LOOKBACK_DAYS} days",
        xaxis_title="date (UTC)",
        yaxis_title="$/GPU·h",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_about() -> None:
    with st.expander("About · methodology"):
        st.markdown(
            """
            **What.** The reference price of a GPU-hour, per model, aggregated across
            multiple marketplaces, with cross-venue dispersion and trend.

            **How.** Canonical index = 20% *trimmed mean* + outlier rejection (MAD),
            24 h window **with no carry-forward**, hyperscalers excluded, lease types kept separate
            (Silicon Data standard / compute futures settlement). Everything is **point-in-time**:
            each value only uses data known at that instant (anti look-ahead).

            **Data.** Real snapshots accumulated continuously, stored in a versioned Parquet
            lake (reproducible). Compute history doesn't exist anywhere else: it is
            built day by day.

            **Free vs. premium.** This dashboard (the *measurement*) is free. Calibrated
            *timing* ("rent now on venue X to minimize cost") is premium.
            """
        )


def render() -> None:
    st.set_page_config(page_title="Compute — Cheapest GPU", page_icon="💸", layout="wide")
    st.title("💸 Cheapest GPU, right now")
    st.caption("Point-in-time multi-venue benchmark · public free tier")

    store = _store()
    model = st.selectbox("GPU model", _available_models(store), index=0)
    as_of = dt.datetime.now(tz=dt.timezone.utc)

    try:
        market = read_market(store, as_of, model)
    except InsufficientDataError:
        st.warning(
            f"No usable reading yet for **{model}**. "
            "History accumulates continuously — check back soon."
        )
        _render_about()
        return

    _render_cheapest(market)
    _render_dispersion(market)
    _render_curve(store, model)
    _render_about()


if __name__ == "__main__":
    render()
