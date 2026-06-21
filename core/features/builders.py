"""Construction de features exogènes **point-in-time** (anti look-ahead strict).

Cœur de la discipline P07. Toute feature à l'instant de décision ``t`` n'utilise
que des observations dont le ``knowledge_ts <= t`` (cf. `protocols`). Le mécanisme
généralise le décalage de publication de `core.pricing.sources.DataFramePriceSource`
(qui décale l'index vers le *connu à t*) en gérant **aussi les révisions** : par
``value_ts``, on ne retient que le dernier millésime publié à temps.

Parallèle assumé avec `core.backtest.guards.LookAheadError` : là-bas un garde-fou
*runtime* pour les signaux de backtest ; ici la même intransigeance au moment de
fabriquer les features. Les deux modules restent découplés (pas d'import croisé).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from core.features.protocols import KNOWLEDGE_TS, VALUE, VALUE_TS, ExogenousSource

# ---------------------------------------------------------------------------
# Lags de publication par défaut — fixés par le directeur de recherche.
#
# Chaque variable exogène n'est connue qu'avec retard. Un lag trop court = look-ahead ;
# trop long = on jette du signal exploitable. Défaut *conservateur* (on préfère
# sur-estimer le retard). À recalibrer sur le vrai calendrier au câblage du connecteur
# réel (cf. CONVERGENCE) ; si la source expose des millésimes, alimenter directement
# les frames vintage (les révisions sont gérées par `as_of_snapshot`).
# ---------------------------------------------------------------------------
DEFAULT_PUBLICATION_LAGS: dict[str, pd.Timedelta] = {
    # Indice gaz de settlement publié J+1 (le day-ahead, lui, serait connu la veille).
    "gas_price": pd.Timedelta("1D"),
    # Température réalisée dispo J+1, + 1 j de marge contre les révisions météo.
    "hdd": pd.Timedelta("2D"),
    "cdd": pd.Timedelta("2D"),  # idem HDD (même source température réalisée).
}


class LookAheadError(RuntimeError):
    """Levée quand une feature à ``t`` consommerait une donnée connue après ``t``."""


def _to_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    """Valide qu'un index est temporel tz-aware et le ramène en UTC.

    Réplique locale de la règle d'intégrité du labo (cf.
    ``core.pricing._timeindex.to_utc_index``) pour garder `core.features`
    auto-suffisant. Convergence : promouvoir ce helper dans ``core.utils``.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("l'index doit être un DatetimeIndex")
    if index.tz is None:
        raise ValueError("datetime naïf interdit : index UTC tz-aware obligatoire")
    return index.tz_convert("UTC")


def from_lagged_series(
    values: pd.Series,
    publication_lag: pd.Timedelta,
) -> pd.DataFrame:
    """Fabrique un frame vintage depuis une série simple + un lag de publication.

    Cas PoC sans vrais millésimes : on pose ``knowledge_ts = value_ts + lag``. Les
    révisions, elles, se modélisent en concaténant plusieurs lignes de même
    ``value_ts`` (knowledge_ts distincts) directement dans le frame vintage.

    Parameters
    ----------
    values
        Série indexée par ``value_ts`` (DatetimeIndex tz-aware) → valeur observée.
    publication_lag
        Retard entre la période décrite et sa publication (``Timedelta``).

    Returns
    -------
    pd.DataFrame
        Colonnes ``(value_ts, knowledge_ts, value)``, horodatages UTC.
    """
    value_ts = _to_utc_index(values.index)
    return pd.DataFrame(
        {
            VALUE_TS: value_ts,
            KNOWLEDGE_TS: value_ts + publication_lag,
            VALUE: values.to_numpy(dtype=float),
        }
    )


def as_of_snapshot(vintages: pd.DataFrame, asof: pd.Timestamp) -> pd.Series:
    """Snapshot point-in-time : valeurs connues à ``asof`` (lag + révisions gérés).

    1. ne garde que les lignes ``knowledge_ts <= asof`` (filtre de publication) ;
    2. par ``value_ts``, retient le ``knowledge_ts`` le plus récent (dernier
       millésime connu — gère les révisions) ;
    3. renvoie une série indexée par ``value_ts`` croissant.

    Une série vide (rien encore publié) est renvoyée avec un index UTC vide.
    """
    known = vintages[vintages[KNOWLEDGE_TS] <= asof]
    if known.empty:
        empty_index = pd.DatetimeIndex([], tz="UTC", name=VALUE_TS)
        return pd.Series([], index=empty_index, dtype=float)

    latest_rows = known.loc[known.groupby(VALUE_TS)[KNOWLEDGE_TS].idxmax()]
    snapshot = pd.Series(
        latest_rows[VALUE].to_numpy(dtype=float),
        index=pd.DatetimeIndex(latest_rows[VALUE_TS], name=VALUE_TS),
        dtype=float,
    )
    return snapshot.sort_index()


def assert_point_in_time(asof: pd.Timestamp, used_knowledge_ts: pd.Series) -> None:
    """Garde-fou : lève `LookAheadError` si un ``knowledge_ts`` utilisé dépasse ``asof``.

    Pendant features du garde-fou backtest : rend le look-ahead **impossible à
    ignorer** plutôt que de le corriger silencieusement.
    """
    offenders = used_knowledge_ts[used_knowledge_ts > asof]
    if not offenders.empty:
        raise LookAheadError(
            f"{len(offenders)} donnée(s) non connue(s) à {asof} : "
            f"knowledge_ts max = {offenders.max()}"
        )


def lag_feature(snapshot: pd.Series, k: int) -> float:
    """Valeur retardée de ``k`` pas dans le snapshot connu (lag 0 = plus récente)."""
    if k < 0:
        raise ValueError(f"lag négatif interdit : k={k}")
    if k >= snapshot.shape[0]:
        return math.nan
    return float(snapshot.iloc[-1 - k])


def rolling_mean_feature(snapshot: pd.Series, window: int) -> float:
    """Moyenne des ``window`` dernières valeurs connues (NaN si historique trop court)."""
    if window <= 0:
        raise ValueError(f"fenêtre invalide : window={window}")
    if snapshot.shape[0] < window:
        return math.nan
    return float(snapshot.iloc[-window:].mean())


def diff_feature(snapshot: pd.Series, k: int) -> float:
    """Différence entre la valeur la plus récente et celle retardée de ``k``."""
    latest = lag_feature(snapshot, 0)
    lagged = lag_feature(snapshot, k)
    if math.isnan(latest) or math.isnan(lagged):
        return math.nan
    return latest - lagged


@dataclass(frozen=True)
class FeatureSpec:
    """Quelles features dériver d'une variable (toutes ≤ t par construction)."""

    lags: tuple[int, ...] = ()
    rolling_means: tuple[int, ...] = ()
    diffs: tuple[int, ...] = ()


class PointInTimeFeatureBuilder:
    """Builder point-in-time injectable (implémente `FeatureBuilder`).

    Parameters
    ----------
    source
        Source exogène (protocole `ExogenousSource`) servant les frames vintage.
    specs
        Pour chaque variable, la `FeatureSpec` des transforms à dériver.
    """

    def __init__(self, source: ExogenousSource, specs: dict[str, FeatureSpec]) -> None:
        self._source = source
        self._specs = specs

    def _feature_plan(self) -> list[tuple[str, str, str, int]]:
        """Liste ordonnée et déterministe ``(nom_feature, variable, kind, param)``."""
        plan: list[tuple[str, str, str, int]] = []
        for name, spec in self._specs.items():
            plan += [(f"{name}_lag{k}", name, "lag", k) for k in spec.lags]
            plan += [(f"{name}_roll{w}", name, "roll", w) for w in spec.rolling_means]
            plan += [(f"{name}_diff{k}", name, "diff", k) for k in spec.diffs]
        return plan

    def build_asof(self, asof: pd.Timestamp) -> pd.Series:
        snapshots = {
            name: as_of_snapshot(self._source.vintages(name), asof) for name in self._specs
        }
        values: dict[str, float] = {}
        for feat_name, var, kind, param in self._feature_plan():
            snap = snapshots[var]
            if kind == "lag":
                values[feat_name] = lag_feature(snap, param)
            elif kind == "roll":
                values[feat_name] = rolling_mean_feature(snap, param)
            else:  # diff
                values[feat_name] = diff_feature(snap, param)
        return pd.Series(values, dtype=float)

    def build_panel(self, decision_index: pd.DatetimeIndex) -> pd.DataFrame:
        columns = [name for name, _, _, _ in self._feature_plan()]
        rows = [self.build_asof(t) for t in decision_index]
        return pd.DataFrame(rows, index=decision_index, columns=columns)


__all__ = [
    "DEFAULT_PUBLICATION_LAGS",
    "LookAheadError",
    "as_of_snapshot",
    "from_lagged_series",
    "assert_point_in_time",
    "lag_feature",
    "rolling_mean_feature",
    "diff_feature",
    "FeatureSpec",
    "PointInTimeFeatureBuilder",
    # ré-exports pratiques
    "KNOWLEDGE_TS",
    "VALUE",
    "VALUE_TS",
]
