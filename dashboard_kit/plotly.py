"""Shared Plotly template built from :mod:`dashboard_kit.tokens`.

One template for every chart in the lab, so two dashboards opened side by side read as the
same instrument. Registering it under a name means an ``app.py`` sets
``template=DESK_TEMPLATE`` and inherits fonts, grid, hover and number formats — it never
restates a colour.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

import plotly.graph_objects as go
import plotly.io as pio

from .tokens import COLORS, COLORWAY, FONTS, SIZES

#: Name under which the template is registered in ``plotly.io.templates``.
DESK_TEMPLATE: Final[str] = "compute_desk"

#: Tick format for money axes ($/GPU·h) — two decimals, no thousands noise.
MONEY_TICKFORMAT: Final[str] = "$,.2f"
#: Hover format for money values, slightly more precise than the axis.
MONEY_HOVERFORMAT: Final[str] = "$,.4f"
#: Ticks targeted per axis when deriving adaptive precision — enough decimals that this
#: many evenly-spaced ticks across the observed range render as distinct labels.
_ADAPTIVE_TICK_COUNT: Final[int] = 6
#: Decimal-place bounds for adaptive money ticks: never coarser than whole cents, never
#: so fine that the label turns into noise.
_MIN_DECIMALS: Final[int] = 2
_MAX_DECIMALS: Final[int] = 5


def _adaptive_money_tickformat(values: Sequence[float]) -> str:
    """Pick a ``$,.Nf`` tick format with enough decimals for a narrow-range series.

    A fixed 2-decimal format is fine when the series spans dollars, but collapses every
    tick to the same label when it varies in the third decimal or below (e.g. a spot
    index oscillating between $1.455 and $1.465). Decimals are derived from the span
    (max - min) of ``values``, not from any single value, so a narrow range gets more
    precision regardless of the series' absolute level.
    """
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if len(finite) < 2:
        return MONEY_TICKFORMAT
    span = max(finite) - min(finite)
    if span <= 0:
        return MONEY_TICKFORMAT
    # Decimals needed so ~_ADAPTIVE_TICK_COUNT ticks across the span differ once rounded.
    step = span / _ADAPTIVE_TICK_COUNT
    decimals = max(_MIN_DECIMALS, -math.floor(math.log10(step)))
    decimals = min(_MAX_DECIMALS, int(decimals))
    return f"$,.{decimals}f"


def _build_template() -> go.layout.Template:
    """Assemble the desk template from the design tokens."""
    axis = dict(
        gridcolor=COLORS["border"],
        zerolinecolor=COLORS["border"],
        linecolor=COLORS["border"],
        tickcolor=COLORS["border"],
        tickfont=dict(color=COLORS["muted"], size=11),
        title=dict(font=dict(color=COLORS["muted"], size=12)),
        showline=True,
        automargin=True,
    )
    return go.layout.Template(
        layout=dict(
            colorway=list(COLORWAY),
            paper_bgcolor=COLORS["surface"],
            plot_bgcolor=COLORS["surface"],
            font=dict(family=FONTS["sans"], color=COLORS["text"], size=13),
            title=dict(
                font=dict(family=FONTS["sans"], color=COLORS["text"], size=16),
                x=0.0,
                xanchor="left",
                pad=dict(b=12),
            ),
            margin=dict(l=56, r=24, t=48, b=48),
            height=SIZES["chart_height"],
            xaxis={**axis, "showgrid": False},
            yaxis={**axis, "showgrid": True, "griddash": "dot"},
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0.0,
                font=dict(color=COLORS["muted"], size=11),
                bgcolor="rgba(0,0,0,0)",
            ),
            hoverlabel=dict(
                bgcolor=COLORS["bg"],
                bordercolor=COLORS["border"],
                font=dict(family=FONTS["mono"], color=COLORS["text"], size=12),
            ),
            hovermode="x unified",
        )
    )


def register_template() -> str:
    """Register the desk template and make it Plotly's default (idempotent).

    Setting it as the default means a figure inherits the desk styling without every
    call site restating ``template=``; passing it explicitly stays valid.
    """
    pio.templates[DESK_TEMPLATE] = _build_template()
    pio.templates.default = DESK_TEMPLATE
    return DESK_TEMPLATE


def money_axis(
    fig: go.Figure, *, title: str = "$/GPU·h", values: Sequence[float] | None = None
) -> go.Figure:
    """Apply the money tick/hover format to ``fig``'s y-axis. Returns ``fig``.

    ``values`` is optional: pass the y-series actually plotted (e.g. ``curve["price"]``)
    to derive tick precision from its span, so a narrow-range series (a spot index barely
    moving over a window) doesn't render every tick as the same rounded label. Omitting
    it keeps the fixed two-decimal :data:`MONEY_TICKFORMAT`.
    """
    tickformat = _adaptive_money_tickformat(values) if values is not None else MONEY_TICKFORMAT
    fig.update_yaxes(title_text=title, tickformat=tickformat, hoverformat=MONEY_HOVERFORMAT)
    return fig


__all__ = [
    "DESK_TEMPLATE",
    "MONEY_HOVERFORMAT",
    "MONEY_TICKFORMAT",
    "money_axis",
    "register_template",
]
