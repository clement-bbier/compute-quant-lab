"""Design tokens — the single source of truth for the lab's UI styling.

Deliberately **outside** ``core/``: ``core`` is the quant library (pricing, features,
backtest) and carries no presentation concern. Anything here is about how a number is
*shown*, never about what the number *is*.

The palette is a dark "desk terminal" register: a near-black canvas, lifted surfaces for
panels, one cool accent for the canonical series, and red/green reserved **strictly** for
market semantics (never for decoration). Values are plain hex strings in a plain dict so
the future showcase site (V6) can import :data:`TOKENS` and re-export it as JSON/CSS
without pulling Plotly or Streamlit along.
"""

from __future__ import annotations

from typing import Final

#: Named palette. Keys are stable — treat them as the public contract of this module.
COLORS: Final[dict[str, str]] = {
    # -- canvas ---------------------------------------------------------------
    "bg": "#0F1115",  # page background
    "surface": "#171A21",  # cards, plot paper, table rows
    "border": "#262B36",  # hairlines, grid, axis lines
    # -- ink ------------------------------------------------------------------
    "text": "#E6E9EF",  # primary copy, KPI values
    "muted": "#8A93A6",  # captions, axis ticks, secondary labels
    # -- meaning --------------------------------------------------------------
    "accent": "#4DA3FF",  # the canonical index: the one thing that matters
    "up": "#2ED47A",  # cheaper / favourable move
    "down": "#FF5C5C",  # pricier / adverse move
    "warn": "#F2B24C",  # staleness, thin history, caveats
}

#: Categorical series order (venue clouds, multi-line charts). Accent stays reserved for
#: the index, so it is deliberately *absent* here: a venue must never look canonical.
COLORWAY: Final[tuple[str, ...]] = (
    "#7C8AA5",
    "#5FB3B3",
    "#B08BD4",
    "#D49A6A",
    "#6A9FD4",
    "#9AAE7B",
    "#C77B9E",
    "#8A93A6",
)

#: Typography. Streamlit only accepts a family class in ``config.toml``; the mono stack is
#: applied to numerals via the CSS block in :mod:`dashboard_kit.streamlit`.
FONTS: Final[dict[str, str]] = {
    "sans": (
        '"Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif'
    ),
    "mono": '"JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace',
}

#: Spacing / sizing scale, in px unless noted. Keeps chart heights and gutters consistent
#: across both apps instead of each ``app.py`` inventing its own numbers.
SIZES: Final[dict[str, int]] = {
    "chart_height": 420,
    "chart_height_short": 360,
    "radius": 8,
    "gutter": 16,
}

#: Flat, JSON-serialisable export. This is what V6 consumes.
TOKENS: Final[dict[str, object]] = {
    "colors": COLORS,
    "colorway": list(COLORWAY),
    "fonts": FONTS,
    "sizes": SIZES,
}

__all__ = ["COLORS", "COLORWAY", "FONTS", "SIZES", "TOKENS"]
