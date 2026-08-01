"""Shared Plotly template built from :mod:`dashboard_kit.tokens`.

One template for every chart in the lab, so two dashboards opened side by side read as the
same instrument. Registering it under a name means an ``app.py`` sets
``template=DESK_TEMPLATE`` and inherits fonts, grid, hover and number formats — it never
restates a colour.
"""

from __future__ import annotations

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


def money_axis(fig: go.Figure, *, title: str = "$/GPU·h") -> go.Figure:
    """Apply the money tick/hover format to ``fig``'s y-axis. Returns ``fig``."""
    fig.update_yaxes(title_text=title, tickformat=MONEY_TICKFORMAT, hoverformat=MONEY_HOVERFORMAT)
    return fig


__all__ = [
    "DESK_TEMPLATE",
    "MONEY_HOVERFORMAT",
    "MONEY_TICKFORMAT",
    "money_axis",
    "register_template",
]
