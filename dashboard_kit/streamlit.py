"""Streamlit page setup: config, chrome hiding, and the lab's single CSS block.

Every style rule the dashboards need lives in :func:`_css` — one block, injected once by
:func:`apply_page`. The rule for contributors: an ``app.py`` calls ``apply_page(...)`` and
then writes only content. If a new visual need appears, it is added here, not inlined at
the call site.
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

from .plotly import register_template
from .tokens import COLORS, FONTS, SIZES


def _css() -> str:
    """The lab's stylesheet. Single source of every CSS rule across both dashboards."""
    return f"""
    <style>
      /* -- chrome: hide the Streamlit menu/footer/deploy affordances ----------- */
      #MainMenu, footer, header [data-testid="stToolbar"],
      [data-testid="stDecoration"] {{ visibility: hidden; }}
      footer {{ height: 0; }}

      /* -- canvas ------------------------------------------------------------- */
      .stApp {{ background: {COLORS["bg"]}; }}
      .block-container {{ padding-top: 2.4rem; max-width: 1500px; }}
      h1, h2, h3 {{ font-family: {FONTS["sans"]}; letter-spacing: -0.01em; }}
      h1 {{ font-size: 1.75rem; font-weight: 650; }}
      h2, h3 {{ font-size: 1.05rem; font-weight: 600; color: {COLORS["text"]}; }}

      /* -- KPI metric cards --------------------------------------------------- */
      [data-testid="stMetric"] {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border"]};
        border-radius: {SIZES["radius"]}px;
        padding: 14px 18px;
      }}
      [data-testid="stMetricLabel"] {{
        color: {COLORS["muted"]};
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
      }}
      [data-testid="stMetricValue"] {{
        font-family: {FONTS["mono"]};
        font-size: 1.5rem;
        color: {COLORS["text"]};
      }}
      [data-testid="stMetricDelta"] {{ font-family: {FONTS["mono"]}; font-size: 0.8rem; }}

      /* -- tabular numerals in dataframes ------------------------------------- */
      [data-testid="stDataFrame"] {{ font-family: {FONTS["mono"]}; font-size: 0.85rem; }}

      /* -- callouts ----------------------------------------------------------- */
      [data-testid="stAlert"] {{
        border-radius: {SIZES["radius"]}px;
        border: 1px solid {COLORS["border"]};
      }}
      [data-testid="stCaptionContainer"] {{ color: {COLORS["muted"]}; }}
    </style>
    """


def apply_page(*, title: str, icon: str, layout: Literal["centered", "wide"] = "wide") -> str:
    """Configure the page, inject the stylesheet, register the Plotly template.

    The one call an ``app.py`` makes before rendering anything. Returns the Plotly
    template name so charts can pass ``template=`` without importing the tokens.
    """
    st.set_page_config(page_title=title, page_icon=icon, layout=layout)
    st.markdown(_css(), unsafe_allow_html=True)
    return register_template()


def header(title: str, caption: str) -> None:
    """Standard page header: title then a muted one-line caption."""
    st.title(title)
    st.caption(caption)


__all__ = ["apply_page", "header"]
