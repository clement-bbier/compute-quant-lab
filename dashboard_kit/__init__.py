"""Presentation layer for the lab's Streamlit dashboards.

Sits outside ``core/`` on purpose: ``core`` is the quant library and holds no styling.
This package holds the design tokens, the shared Plotly template and the Streamlit page
chrome, so both dashboards (and, later, the showcase site) render as one instrument.

Typical use in an ``app.py``::

    from dashboard_kit import COLORS, apply_page, header, money_axis

    template = apply_page(title="Compute Spot Benchmark", icon="⚡")
    header("Compute Spot Benchmark", "Multi-venue GPU-hour reference price")
"""

from __future__ import annotations

from .plotly import (
    DESK_TEMPLATE,
    MONEY_HOVERFORMAT,
    MONEY_TICKFORMAT,
    money_axis,
    register_template,
)
from .streamlit import apply_page, header
from .tokens import COLORS, COLORWAY, FONTS, SIZES, TOKENS

__all__ = [
    "COLORS",
    "COLORWAY",
    "DESK_TEMPLATE",
    "FONTS",
    "MONEY_HOVERFORMAT",
    "MONEY_TICKFORMAT",
    "SIZES",
    "TOKENS",
    "apply_page",
    "header",
    "money_axis",
    "register_template",
]
