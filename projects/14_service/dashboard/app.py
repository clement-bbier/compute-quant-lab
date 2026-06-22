"""Dashboard public « GPU le moins cher maintenant » — la vitrine gratuite (free tier).

Couche I/O isolée (Streamlit) : aucune logique métier ici, tout est délégué à ``src/``
(``views`` pour la mesure, ``signal_iface``/``alerts`` pour la reco). Lit le **cold store
versionné** (``core.storage``). Dégrade proprement quand l'historique est maigre.

Frontière edge : on n'affiche que la **mesure** (qui est le moins cher, à quel niveau,
quelle tendance) et une **reco heuristique gratuite** explicitement étiquetée non-edge.
Le **timing calibré** (premium) vit dans ``private/`` et n'apparaît jamais ici.

Lancement : ``streamlit run projects/14_service/dashboard/app.py``.
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

# Rend les modules produit (sous src/) importables hors pytest (après les imports stables).
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from signal_iface import Action, NaiveSignalSource  # noqa: E402  (après ajout sys.path)
from views import MarketView, price_curve, read_market  # noqa: E402

#: Modèles proposés au sélecteur (présents ou non dans le lac — géré à l'affichage).
CANDIDATE_MODELS: list[str] = ["H100", "H200", "B200", "A100", "L40S", "RTX4090"]
#: Profondeur de la courbe de tendance (jours).
CURVE_LOOKBACK_DAYS: int = 30


def _store() -> ParquetSnapshotStore:
    return ParquetSnapshotStore(SNAPSHOTS_DIR)


def _render_cheapest(market: MarketView) -> None:
    cheapest = market.cheapest
    col1, col2, col3 = st.columns(3)
    col1.metric("Venue la moins chère", cheapest.source, f"{cheapest.rate:.2f} $/GPU·h")
    col2.metric("Indice canonique", f"{market.index_price:.2f} $/GPU·h", help=market.method)
    col3.metric("Venues retenues", str(len(market.venues)))

    naive = NaiveSignalSource().assess(market)
    badge = "🟢 LOUER MAINTENANT" if naive.action is Action.RENT_NOW else "⏸️ ATTENDRE"
    st.info(
        f"**Reco gratuite : {badge}** — {naive.rationale}\n\n"
        "_Heuristique publique non calibrée. Le **timing calibré** (quand louer pour "
        "minimiser le coût) est un service **premium**._"
    )


def _render_dispersion(market: MarketView) -> None:
    cheapest_rate = market.cheapest.rate
    rows = [
        {
            "venue": v.source,
            "$/GPU·h": round(v.rate, 4),
            "écart vs moins chère": f"+{(v.rate / cheapest_rate - 1) * 100:.1f} %",
            "dispo (GPU)": v.availability,
        }
        for v in market.venues
    ]
    st.subheader("Dispersion inter-venues")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_curve(store: ParquetSnapshotStore, model: str) -> None:
    now = pd.Timestamp.now(tz="UTC")
    timestamps = list(pd.date_range(end=now, periods=CURVE_LOOKBACK_DAYS, freq="D").to_pydatetime())
    curve = price_curve(store, model, timestamps)
    if curve["index_price"].isna().all():
        st.caption("Pas encore assez d'historique pour tracer la tendance.")
        return
    fig = go.Figure(go.Scatter(x=curve["as_of"], y=curve["index_price"], mode="lines+markers"))
    fig.update_layout(
        title=f"Indice spot {model} — {CURVE_LOOKBACK_DAYS} derniers jours",
        xaxis_title="date (UTC)",
        yaxis_title="$/GPU·h",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_about() -> None:
    with st.expander("À propos · méthodologie"):
        st.markdown(
            """
            **Quoi.** Le prix de référence d'une heure-GPU, par modèle, agrégé sur
            plusieurs marketplaces, avec la dispersion inter-venues et la tendance.

            **Comment.** Indice canonique = *trimmed mean* 20 % + rejet d'outliers (MAD),
            fenêtre 24 h **sans carry-forward**, hyperscalers exclus, types de bail séparés
            (standard Silicon Data / settlement futures compute). Tout est **point-in-time** :
            chaque valeur n'utilise que la donnée connue à cet instant (anti look-ahead).

            **Données.** Snapshots réels accumulés en continu, stockés dans un lac Parquet
            versionné (reproductible). L'historique compute n'existe pas ailleurs : il se
            fabrique jour après jour.

            **Gratuit vs premium.** Ce tableau de bord (la *mesure*) est gratuit. Le *timing*
            calibré (« louer maintenant sur telle venue pour minimiser le coût ») est premium.
            """
        )


def render() -> None:
    st.set_page_config(page_title="Compute — GPU le moins cher", page_icon="💸", layout="wide")
    st.title("💸 GPU le moins cher, maintenant")
    st.caption("Benchmark multi-venues point-in-time · free tier public")

    store = _store()
    model = st.selectbox("Modèle GPU", CANDIDATE_MODELS, index=0)
    as_of = dt.datetime.now(tz=dt.timezone.utc)

    try:
        market = read_market(store, as_of, model)
    except InsufficientDataError:
        st.warning(
            f"Pas encore de relevé exploitable pour **{model}**. "
            "L'historique s'accumule en continu — revenez bientôt."
        )
        _render_about()
        return

    _render_cheapest(market)
    _render_dispersion(market)
    _render_curve(store, model)
    _render_about()


render()
