"""Tests of the energy cold store (idempotence + point-in-time integrity)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from core.storage.energy_store import EnergyColdStore


def _frame() -> pd.DataFrame:
    pt = pd.Timestamp("2024-01-14T18:00:00Z")
    it = pd.Timestamp("2024-01-15T06:00:00Z")
    return pd.DataFrame(
        {
            "source": ["ercot", "ercot"],
            "series": ["load_forecast", "net_load_forecast"],
            "publish_time": [pt, pt],
            "interval_start": [it, it],
            "value": [45000.0, 38000.0],
        }
    )


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    assert store.write(_frame()) == 2
    out = store.read()
    assert len(out) == 2
    assert set(out["series"]) == {"load_forecast", "net_load_forecast"}
    assert str(out["publish_time"].dt.tz) == "UTC"


def test_write_is_idempotent(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    assert store.write(_frame()) == 0  # rewriting the same content = no-op
    assert len(store.read()) == 2


def test_read_filters_series(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    out = store.read(series="load_forecast")
    assert set(out["series"]) == {"load_forecast"}
    assert len(out) == 1


def test_rejects_naive_timestamp(tmp_path: Path) -> None:
    bad = _frame()
    bad["interval_start"] = pd.Timestamp("2024-01-15T06:00:00")  # naive -> forbidden
    with pytest.raises(ValueError, match="naive"):
        EnergyColdStore(tmp_path).write(bad)


def test_read_empty_lake_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    store = EnergyColdStore(tmp_path)
    with caplog.at_level(logging.WARNING):
        out = store.read()
    assert out.empty
    assert "empty" in caplog.text.lower()


def test_write_logs_new_rows_and_dedup_count(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = EnergyColdStore(tmp_path)
    with caplog.at_level(logging.INFO):
        store.write(_frame())
    assert "2 new row" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO):
        store.write(_frame())  # same content -> fully deduplicated
    assert "0 new row" in caplog.text
    assert "2 already present" in caplog.text


def test_new_publish_time_appends(tmp_path: Path) -> None:
    # A revision (more recent publish_time) of the same interval is kept (journal).
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    revised = _frame().iloc[[0]].copy()
    revised["publish_time"] = pd.Timestamp("2024-01-14T19:00:00Z")
    revised["value"] = 46000.0
    assert store.write(revised) == 1
    assert len(store.read(series="load_forecast")) == 2


# -- Point-in-time reads (`as_of`, V7.3) ----------------------------------------


def test_read_as_of_none_returns_everything(tmp_path: Path) -> None:
    """Default (no as_of) is unchanged from pre-V7.3 behaviour: full backward compat."""
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    assert len(store.read(as_of=None)) == 2


def test_read_as_of_excludes_rows_published_after_cutoff(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())  # both rows publish_time = 2024-01-14T18:00:00Z

    before_publish = pd.Timestamp("2024-01-14T17:59:59Z")
    assert store.read(as_of=before_publish).empty


def test_read_as_of_boundary_is_inclusive(tmp_path: Path) -> None:
    """A row published exactly at as_of is known at as_of: kept, not excluded."""
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    publish_time = pd.Timestamp("2024-01-14T18:00:00Z")

    out = store.read(as_of=publish_time)

    assert len(out) == 2


def test_read_as_of_one_second_after_boundary_still_includes_row(tmp_path: Path) -> None:
    """One instant later, the same rows are still known (publish_time <= as_of)."""
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    just_after = pd.Timestamp("2024-01-14T18:00:01Z")

    out = store.read(as_of=just_after)

    assert len(out) == 2


def test_read_as_of_distinguishes_revisions(tmp_path: Path) -> None:
    """A revision published later must not leak into an as_of before its publish_time."""
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    revised = _frame().iloc[[0]].copy()
    revised["publish_time"] = pd.Timestamp("2024-01-14T19:00:00Z")
    revised["value"] = 46000.0
    store.write(revised)

    as_of_before_revision = pd.Timestamp("2024-01-14T18:30:00Z")
    out = store.read(series="load_forecast", as_of=as_of_before_revision)

    assert len(out) == 1
    assert out["value"].iloc[0] == 45000.0  # only the original vintage was known then


def test_read_as_of_rejects_naive_cutoff(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    with pytest.raises(ValueError, match="naive"):
        store.read(as_of=pd.Timestamp("2024-01-14T18:00:00"))


# -- Provenance (`simulated`, `ingested_at`, V7.3) -------------------------------


def test_write_stamps_ingested_at_forward_only(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    out = store.read()
    assert out["ingested_at"].notna().all()
    assert str(out["ingested_at"].dt.tz) == "UTC"


def test_write_stamps_simulated_false(tmp_path: Path) -> None:
    """Every backfill collector wired today (ENTSO-E, ERCOT) reads a real market."""
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    out = store.read()
    assert (out["simulated"] == False).all()  # noqa: E712


def test_read_backfills_simulated_and_ingested_at_for_legacy_rows(tmp_path: Path) -> None:
    """A row predating these columns backfills to False/NaT, not rejected."""
    from core.storage.energy_store import _MONTH, _PARTITIONING  # noqa: PLC0415

    import pyarrow as pa  # noqa: PLC0415
    import pyarrow.dataset as pads  # noqa: PLC0415

    legacy = _frame()
    legacy[_MONTH] = legacy["interval_start"].dt.strftime("%Y%m")
    table = pa.Table.from_pandas(legacy, preserve_index=False)
    pads.write_dataset(table, tmp_path, format="parquet", partitioning=_PARTITIONING)

    out = EnergyColdStore(tmp_path).read()

    assert (out["simulated"] == False).all()  # noqa: E712
    assert out["ingested_at"].isna().all()
