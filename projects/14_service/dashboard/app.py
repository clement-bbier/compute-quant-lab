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
from collections import defaultdict
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.ingestion.compute_index import InsufficientDataError
from core.ingestion.protocols import SnapshotStore
from core.storage import ParquetSnapshotStore
from core.utils.config import SNAPSHOTS_DIR
from dashboard_kit import COLORS, SIZES, apply_page, header, money_axis

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
#: A model is offered only if this many venues quote it (cross-venue comparison needs ≥2).
_MIN_VENUES: int = 2


def _store() -> ParquetSnapshotStore:
    return ParquetSnapshotStore(SNAPSHOTS_DIR)


def _available_models(store: SnapshotStore) -> list[str]:
    """GPU models worth offering: those quoted by at least two venues, most-covered first.

    The lake also holds raw single-venue SKUs (``1XB300SXM6262GB`` and the like). Listing
    them alphabetically put an uncomparable SKU first, so the page opened on an empty
    market. A cross-venue benchmark is only meaningful where several venues quote the same
    model, which is exactly the filter applied here.
    """
    venues_by_model: dict[str, set[str]] = defaultdict(set)
    for s in store.load():
        venues_by_model[s.gpu_model].add(s.source)
    ranked = sorted(
        (m for m, venues in venues_by_model.items() if len(venues) >= _MIN_VENUES),
        key=lambda m: (-len(venues_by_model[m]), m),
    )
    return ranked or _FALLBACK_MODELS


def _fix_instant(store: SnapshotStore) -> dt.datetime:
    """Instant the dashboard reads the market at: the lake's most recent observation.

    Wall-clock ``now`` would blank every view on any clone whose committed lake is more
    than the staleness window old (no carry-forward, by design). Anchoring on the latest
    stored observation keeps the page populated without weakening point-in-time: nothing
    later than the returned instant exists in the store, so no future data can leak in.
    """
    stored = [s.snapshotted_at for s in store.load()]
    return max(stored) if stored else dt.datetime.now(tz=dt.timezone.utc)


def _render_fix_age(as_of: dt.datetime) -> None:
    """State which instant is displayed, and how far behind live it is."""
    age = dt.datetime.now(tz=dt.timezone.utc) - as_of
    stamp = as_of.strftime("%Y-%m-%d %H:%M UTC")
    if age > dt.timedelta(days=1):
        st.caption(
            f"Fix **{stamp}** — latest reading in the versioned lake, "
            f"{age.days} d behind live. Collection is continuous; a fresh clone "
            "shows the last committed fix."
        )
    else:
        st.caption(f"Fix **{stamp}** — live.")


def _render_cheapest(market: MarketView) -> None:
    cheapest = market.cheapest
    discount = cheapest.rate / market.index_price - 1
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cheapest venue", cheapest.source, f"{cheapest.rate:.2f} $/GPU·h")
    col2.metric(
        "Discount vs index",
        f"{discount:+.1%}",
        help="Cheapest venue against the canonical index — negative is cheaper.",
    )
    col3.metric("Canonical index", f"{market.index_price:.2f} $/GPU·h", help=market.method)
    col4.metric("Venues retained", str(len(market.venues)))

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
    fig = go.Figure(
        go.Scatter(
            x=curve["as_of"],
            y=curve["index_price"],
            mode="lines+markers",
            line=dict(width=2.5, color=COLORS["accent"]),
            marker=dict(size=5, color=COLORS["accent"]),
            name="index",
        )
    )
    fig.update_layout(
        title=f"{model} spot index — last {CURVE_LOOKBACK_DAYS} days",
        xaxis_title="date (UTC)",
        height=SIZES["chart_height_short"],
    )
    money_axis(fig)
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
    apply_page(title="Compute — Cheapest GPU", icon="💸")
    header(
        "Cheapest GPU, right now",
        "Point-in-time multi-venue benchmark · public free tier",
    )

    store = _store()
    model = st.selectbox("GPU model", _available_models(store), index=0)
    as_of = _fix_instant(store)
    _render_fix_age(as_of)

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
