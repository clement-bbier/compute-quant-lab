"""Tests TDD : schéma enrichi et rétrocompatibilité de normalize_frame.

Couvre :
- (b) ``normalize_frame`` backfille un frame/Parquet legacy sans les nouvelles
  colonnes descriptives (preuve de rétrocompatibilité).
- Propagation des champs optionnels dans le round-trip ``Snapshot ↔ frame``.
- Les colonnes optionnelles sont bien présentes dans la sortie de normalize_frame,
  même si elles n'étaient pas dans l'entrée.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from core.ingestion.protocols import Snapshot
from core.storage.converters import frame_to_snapshots, snapshots_to_frame
from core.storage.schema import (
    ALL_COLUMNS,
    AVAILABILITY,
    COLUMNS,
    DISK_GB,
    GPU_MEMORY_GB,
    GPU_MODEL,
    LEASE_TYPE,
    OPTIONAL_COLUMNS,
    PRICE,
    PROVIDER_DETAIL,
    RAM_GB,
    REGION,
    SNAPSHOTTED_AT,
    SOURCE,
    VCPU,
    normalize_frame,
)

_TS = pd.Timestamp("2026-01-01", tz="UTC")
_TS_PY = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


# ── (b) Rétrocompatibilité normalize_frame ────────────────────────────────────


def _legacy_frame() -> pd.DataFrame:
    """Frame avec UNIQUEMENT les colonnes obligatoires (format pré-enrichissement)."""
    return pd.DataFrame(
        [
            {
                SNAPSHOTTED_AT: _TS,
                SOURCE: "vastai",
                GPU_MODEL: "H100",
                LEASE_TYPE: "on_demand",
                PRICE: 2.50,
                AVAILABILITY: 8,
            }
        ],
        columns=COLUMNS,
    )


def test_normalize_frame_backfills_missing_optional_columns() -> None:
    """Un frame legacy (sans colonnes optionnelles) ne lève pas d'erreur."""
    legacy = _legacy_frame()
    # Aucune colonne optionnelle dans l'entrée.
    assert not any(c in legacy.columns for c in OPTIONAL_COLUMNS)

    result = normalize_frame(legacy)

    # Toutes les colonnes optionnelles sont maintenant présentes.
    for col in OPTIONAL_COLUMNS:
        assert col in result.columns, f"Colonne '{col}' manquante après normalize_frame"
    # Elles valent None.
    assert result[REGION].iloc[0] is None
    assert result[GPU_MEMORY_GB].iloc[0] is None
    assert result[VCPU].iloc[0] is None
    assert result[RAM_GB].iloc[0] is None
    assert result[DISK_GB].iloc[0] is None
    assert result[PROVIDER_DETAIL].iloc[0] is None


def test_normalize_frame_keeps_optional_when_present() -> None:
    """Les colonnes optionnelles présentes dans le frame sont conservées."""
    frame = _legacy_frame()
    frame[REGION] = "EU"
    frame[GPU_MEMORY_GB] = 80.0

    result = normalize_frame(frame)

    assert result[REGION].iloc[0] == "EU"
    assert result[GPU_MEMORY_GB].iloc[0] == 80.0


def test_normalize_frame_output_has_all_columns_in_order() -> None:
    """La sortie contient exactement ALL_COLUMNS (obligatoires + optionnelles)."""
    result = normalize_frame(_legacy_frame())
    assert list(result.columns) == ALL_COLUMNS


def test_normalize_frame_still_rejects_naive_timestamps() -> None:
    """La rétrocompataibilité n'assouplit pas la règle d'intégrité UTC."""
    legacy = _legacy_frame()
    legacy[SNAPSHOTTED_AT] = legacy[SNAPSHOTTED_AT].dt.tz_localize(None)
    with pytest.raises(ValueError):
        normalize_frame(legacy)


def test_normalize_frame_still_rejects_missing_mandatory_column() -> None:
    legacy = _legacy_frame()
    legacy = legacy.drop(columns=[PRICE])
    with pytest.raises(ValueError):
        normalize_frame(legacy)


# ── Round-trip Snapshot ↔ frame (champs enrichis) ─────────────────────────────


def test_snapshots_to_frame_propagates_optional_fields() -> None:
    s = Snapshot(
        snapshotted_at=_TS_PY,
        source="cudo",
        gpu_model="H100",
        price_usd_per_hour=2.50,
        lease_type="on_demand",
        availability=16,
        region="no-luster-1",
        gpu_memory_gb=80.0,
        vcpu=None,
        ram_gb=None,
        disk_gb=None,
        provider_detail=None,
    )
    frame = snapshots_to_frame([s])
    assert frame[REGION].iloc[0] == "no-luster-1"
    assert frame[GPU_MEMORY_GB].iloc[0] == pytest.approx(80.0)
    assert frame[VCPU].iloc[0] is None


def test_frame_to_snapshots_roundtrips_optional_fields() -> None:
    s_in = Snapshot(
        snapshotted_at=_TS_PY,
        source="primeintellect:datacrunch",
        gpu_model="H100",
        price_usd_per_hour=3.0,
        lease_type="on_demand",
        availability=8,
        region="FIN-01",
        gpu_memory_gb=80.0,
        vcpu=176,
        ram_gb=1480.0,
        disk_gb=2048.0,
        provider_detail="datacrunch",
    )
    frame = snapshots_to_frame([s_in])
    restored = frame_to_snapshots(frame)
    assert len(restored) == 1
    s_out = restored[0]

    assert s_out.region == "FIN-01"
    assert s_out.gpu_memory_gb == pytest.approx(80.0)
    assert s_out.vcpu == 176
    assert s_out.ram_gb == pytest.approx(1480.0)
    assert s_out.disk_gb == pytest.approx(2048.0)
    assert s_out.provider_detail == "datacrunch"


def test_frame_to_snapshots_backfills_none_for_legacy_frame() -> None:
    """Un frame legacy (sans colonnes optionnelles) donne des Snapshot avec None."""
    legacy = _legacy_frame()
    snapshots = frame_to_snapshots(legacy)
    assert len(snapshots) == 1
    s = snapshots[0]
    assert s.region is None
    assert s.gpu_memory_gb is None
    assert s.vcpu is None
    assert s.ram_gb is None
    assert s.disk_gb is None
    assert s.provider_detail is None


def test_snapshots_to_frame_all_none_preserved() -> None:
    """Un Snapshot sans champs optionnels → colonnes None dans le frame."""
    s = Snapshot(
        snapshotted_at=_TS_PY,
        source="runpod",
        gpu_model="A100",
        price_usd_per_hour=1.19,
    )
    frame = snapshots_to_frame([s])
    for col in OPTIONAL_COLUMNS:
        assert frame[col].iloc[0] is None, f"Attendu None pour {col}"
