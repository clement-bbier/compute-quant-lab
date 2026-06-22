"""Dashboard Streamlit de **démo** du benchmark spot compute (lecture du cold store réel).

Rend la **mesure** publiable : courbe de l'indice canonique + dispersion inter-venues
(nuage des venues autour de l'indice, spread %, niveaux moyens nommés). Aucune
recommandation de timing (« louer sur X maintenant ») — c'est la frontière edge.

Lancer : ``uv run streamlit run projects/13_compute_benchmark/dashboard/app.py``.
Ce worktree démarre avec ``data/snapshots`` vide : renseigner dans la barre latérale la
racine d'un cold store peuplé (``git checkout data-snapshots -- data/snapshots`` ou ``dvc pull``).
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Rend le paquet projet `benchmark` (sous src/) importable.
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

CONFIG = DEFAULT_INDEX_CONFIG


@st.cache_data(show_spinner=False)
def _load(root: str) -> list[Snapshot]:
    """Charge les snapshots du cold store (caché par racine)."""
    return ParquetSnapshotStore(root).load()


def _grid(snapshots: list[Snapshot], model: str, cadence: str) -> list[dt.datetime]:
    """Grille de fix selon la cadence choisie (canonique quotidienne vs démo par snapshot)."""
    history = summarize_history(snapshots)
    if cadence.startswith("Quotidien"):
        if history.first_at is None or history.last_at is None:
            return []
        return daily_fix_grid(history.first_at, history.last_at + CONFIG.staleness)
    return observed_fix_grid(snapshots, gpu_model=model)


def _venue_points(snapshots: list[Snapshot], grid: list[dt.datetime], model: str) -> pd.DataFrame:
    """Taux par-venue retenus à chaque fix (nuage de dispersion autour de l'indice)."""
    rows = []
    for as_of in grid:
        for r in CONFIG.outlier_filter.filter(
            venue_rates_at(snapshots, as_of, model, config=CONFIG)
        ):
            rows.append({"as_of": as_of, "source": r.source, "rate": r.rate})
    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="Compute Spot Benchmark", layout="wide")
    st.title("Compute Spot Benchmark — prix de référence GPU-heure")
    st.caption(
        "Indice spot **réel** multi-venues, point-in-time (UTC). Mesure publiée : prix de "
        "référence + dispersion inter-venues. Pas de signal de timing « louer sur X maintenant »."
    )

    root = st.sidebar.text_input("Racine du cold store (Parquet)", value=str(SNAPSHOTS_DIR))
    snapshots = _load(root)

    history = summarize_history(snapshots)
    if not snapshots:
        st.warning(
            "Cold store vide. Peupler le lac puis renseigner sa racine :\n\n"
            "`git checkout data-snapshots -- data/snapshots`  (ou `dvc pull`)."
        )
        return

    st.info(
        f"⚠️ Historique réel : **{history.n_snapshots}** relevés · "
        f"**{history.n_venues}** venues ({', '.join(history.sources)}) · "
        f"**{history.n_distinct_timestamps}** instants · span **{history.span_hours:.1f} h**. "
        "Maigre par construction au début — il grossit jour après jour."
    )

    candidates = multi_venue_models(snapshots) or sorted({s.gpu_model for s in snapshots})
    col_model, col_cad = st.sidebar, st.sidebar
    model = col_model.selectbox("Modèle GPU", candidates)
    cadence = col_cad.radio(
        "Cadence",
        ["Démo (par snapshot observé)", "Quotidien (canonique, settlement)"],
        help="Le produit publié = fix quotidien ; la cadence démo montre l'historique maigre.",
    )

    grid = _grid(snapshots, model, cadence)
    series = build_index_series(snapshots, grid, model, config=CONFIG)
    index_df = series.to_frame()
    venue_df = _venue_points(snapshots, grid, model)

    left, right = st.columns(2)
    with left:
        st.subheader(f"Indice canonique — {model}")
        fig = go.Figure()
        if not venue_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=venue_df["as_of"],
                    y=venue_df["rate"],
                    mode="markers",
                    marker=dict(size=8, opacity=0.55),
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
                    line=dict(width=3),
                    name="indice",
                )
            )
        fig.update_layout(yaxis_title="$/GPU·h", xaxis_title="fix (UTC)", height=420)
        st.plotly_chart(fig, use_container_width=True)
        if series.skipped:
            st.caption(
                f"{len(series.skipped)} fix sans venue fraîche (sautés, pas de carry-forward)."
            )

    with right:
        st.subheader("Niveaux moyens par venue (descriptif)")
        levels = venue_levels(snapshots, grid, model, config=CONFIG)
        if levels:
            st.dataframe(
                pd.DataFrame(
                    {
                        "venue": [lv.source for lv in levels],
                        "niveau moyen $/h": [round(lv.mean_rate, 4) for lv in levels],
                        "escompte moyen vs indice": [
                            f"{lv.mean_discount_vs_index:+.1%}" for lv in levels
                        ],
                        "fix": [lv.n_fixes for lv in levels],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "Mesure descriptive sur la fenêtre — **pas** un signal « louer sur X maintenant »."
            )
        else:
            st.write("Pas assez d'historique pour des niveaux par venue.")


if __name__ == "__main__":
    main()
