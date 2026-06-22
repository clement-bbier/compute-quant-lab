# Serveur MCP `gpu-price` — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exposer l'historique réel des prix GPU (`data/snapshots/`) via un serveur MCP stdio interrogeable par un agent (Claude Code / VSCode).

**Architecture:** Serveur mince + service pur (approche 1). `service.py` contient des fonctions pures qui reçoivent un `PriceStore` injecté et renvoient des dicts JSON-sérialisables ; `server.py` n'est que du câblage FastMCP. La lecture passe par `core.storage.ParquetPriceStore.read(as_of=…)` (point-in-time natif) ; l'outil SQL délègue à `core.storage.query`.

**Tech Stack:** Python 3.11, `mcp` (FastMCP, stdio), pandas, DuckDB, pyarrow, pytest. Spec : `docs/superpowers/specs/2026-06-23-gpu-price-mcp-server-design.md`.

**Branche :** `feat/gpu-price-mcp` (déjà sur `main` post-W1). Zone protégée (`pyproject.toml`, `ci.yml`) **non touchée** → handoff `CONVERGENCE.md`.

---

## Structure des fichiers

- Create: `infra/mcp-servers/gpu-price-server/service.py` — logique pure (5 fonctions + 2 helpers).
- Create: `infra/mcp-servers/gpu-price-server/server.py` — câblage FastMCP/stdio.
- Create: `infra/mcp-servers/gpu-price-server/tests/conftest.py` — sys.path + fixtures de données déterministes.
- Create: `infra/mcp-servers/gpu-price-server/tests/test_service.py` — tests TDD de la logique.
- Create: `infra/mcp-servers/gpu-price-server/tests/test_server.py` — smoke test d'enregistrement des outils.
- Create: `infra/mcp-servers/gpu-price-server/README.md` — provenance + avertissement SQL.
- Create: `infra/mcp-servers/gpu-price-server/CONVERGENCE.md` — handoff zone protégée.
- Delete: `infra/mcp-servers/gpu-price-server/.gitkeep` — remplacé par du vrai code.

---

## Task 1 : Scaffolding, dépendance, docs

**Files:**
- Create: `infra/mcp-servers/gpu-price-server/README.md`
- Create: `infra/mcp-servers/gpu-price-server/CONVERGENCE.md`
- Create: `infra/mcp-servers/gpu-price-server/tests/conftest.py`
- Delete: `infra/mcp-servers/gpu-price-server/.gitkeep`

- [ ] **Step 1 : Installer `mcp` en ad-hoc dans le venv** (zone protégée non touchée)

Run: `uv pip install mcp`
Puis vérifier : `python -c "import mcp; from mcp.server.fastmcp import FastMCP; print('mcp OK')"`
Expected: `mcp OK`

- [ ] **Step 2 : Créer `README.md`**

```markdown
# Serveur MCP `gpu-price`

Expose l'historique **réel** des prix de location GPU (snapshots accumulés dans `data/snapshots/`)
via MCP (stdio). Lecture seule, point-in-time.

| Attribut | Valeur |
| --- | --- |
| Unité | USD par GPU·heure ($/GPU·h) |
| Fuseau | UTC, tz-aware (instant naïf rejeté) |
| Fréquence | snapshot planifié (collecteur `infra/collectors/gpu_price_snapshot.py`) |
| Sources | marketplaces (`source` : vastai, runpod, …) |
| Réel/simulé | **réel** (spot observé) |
| Backend | lac Parquet `core.storage.ParquetPriceStore` sous `data/snapshots/` |

## Outils

- `list_gpu_models(as_of?)` — modèles connus (triés, bornés point-in-time).
- `latest_price(gpu_model, lease_type="on_demand", as_of?)` — dernier prix par source + résumé.
- `price_history(gpu_model, start?, as_of?, source?, lease_type?)` — série temporelle.
- `summary_stats(gpu_model, lease_type?, as_of?)` — count/min/max/mean/median/std + par source.
- `query(sql)` — SQL DuckDB **brut** sur la vue `prices`.

## ⚠️ Sécurité

`query` réutilise `core.storage.query` : **tout le pouvoir DuckDB** (`read_csv`, `COPY … TO`,
`INSTALL httpfs`) reste accessible. Piloté par un LLM, ce serveur peut être détourné par
prompt-injection (écriture/exfiltration de fichiers). **N'exposer qu'à des agents de confiance,
sur poste local.** Aucun garde point-in-time sur `query` (lac brut).
```

- [ ] **Step 3 : Créer `CONVERGENCE.md`**

```markdown
# Handoff convergence — serveur MCP gpu-price

Le module a été écrit **sans toucher la zone protégée** (parallel-ops §7). À appliquer en convergence :

1. **`pyproject.toml`** : ajouter `"mcp>=1.2"` aux `[project].dependencies`.
   (En dev, `mcp` est installé ad-hoc via `uv pip install mcp`.)
2. **`.github/workflows/ci.yml`** : ajouter un job de matrice sur
   `infra/mcp-servers/gpu-price-server/tests`, comme la convergence W1 l'a fait pour
   `core/ingestion/providers/tests`. **Ne pas modifier `testpaths`** (reste `["tests"]`).
3. **`.mcp.json`** : déjà câblé (`gpu-price` → `python … server.py`), aucun changement.

Indépendance : le serveur lit la couche storage et n'appelle jamais `fetch_live_gpu_prices`
ni la couche providers W1 — aucune coordination de code requise.
```

- [ ] **Step 4 : Créer `tests/conftest.py` (sys.path + données déterministes)**

```python
"""Fixtures du serveur MCP gpu-price : un cold store Parquet peuplé de données connues."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

# server.py et service.py vivent dans le dossier parent (exécutés hors package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ingestion.protocols import Snapshot  # noqa: E402
from core.storage import ParquetPriceStore, snapshots_to_frame  # noqa: E402

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
T1 = dt.datetime(2026, 6, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def snapshots() -> list[Snapshot]:
    """6 relevés déterministes : 2 sources, 3 modèles, 2 instants ; vastai a 2 offres H100 à T1."""
    return [
        Snapshot(T0, "vastai", "H100", 2.00, "on_demand", 5),
        Snapshot(T0, "runpod", "H100", 2.20, "on_demand", 3),
        Snapshot(T1, "vastai", "H100", 1.80, "on_demand", 4),
        Snapshot(T1, "vastai", "H100", 1.90, "on_demand", 2),
        Snapshot(T1, "runpod", "H100", 2.10, "on_demand", 1),
        Snapshot(T0, "vastai", "A100", 1.00, "on_demand", 10),
        Snapshot(T1, "vastai", "B200", 3.50, "on_demand", 1),
    ]


@pytest.fixture
def store(tmp_path: Path, snapshots: list[Snapshot]) -> ParquetPriceStore:
    """Cold store Parquet temporaire peuplé des `snapshots`."""
    lake = ParquetPriceStore(tmp_path / "lake")
    lake.write(snapshots_to_frame(snapshots))
    return lake
```

- [ ] **Step 5 : Supprimer le `.gitkeep` et committer**

```bash
git rm infra/mcp-servers/gpu-price-server/.gitkeep
git add infra/mcp-servers/gpu-price-server/README.md \
        infra/mcp-servers/gpu-price-server/CONVERGENCE.md \
        infra/mcp-servers/gpu-price-server/tests/conftest.py
git commit -m "chore(gpu-price): scaffolding serveur MCP (README, handoff, fixtures)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 : `_parse_instant` + `list_gpu_models` (TDD)

**Files:**
- Create: `infra/mcp-servers/gpu-price-server/service.py`
- Create: `infra/mcp-servers/gpu-price-server/tests/test_service.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/test_service.py` :

```python
"""Tests TDD de la logique pure du serveur MCP gpu-price."""
from __future__ import annotations

import pytest

from conftest import T0  # fixture module (sys.path injecté par conftest)
from service import (
    latest_price,
    list_gpu_models,
    price_history,
    run_query,
    summary_stats,
)


def test_list_gpu_models_sorted(store):
    assert list_gpu_models(store) == ["A100", "B200", "H100"]


def test_list_gpu_models_point_in_time(store):
    # B200 n'existe qu'à T1 → exclu si as_of = T0 (anti look-ahead)
    assert list_gpu_models(store, as_of=T0.isoformat()) == ["A100", "H100"]


def test_naive_as_of_rejected(store):
    with pytest.raises(ValueError, match="naïf"):
        list_gpu_models(store, as_of="2026-06-01T12:00:00")


def test_invalid_iso_as_of_rejected(store):
    with pytest.raises(ValueError, match="ISO 8601 invalide"):
        list_gpu_models(store, as_of="pas-une-date")


def test_empty_store_graceful(tmp_path):
    from core.storage import ParquetPriceStore

    empty = ParquetPriceStore(tmp_path / "empty")
    assert list_gpu_models(empty) == []
```

- [ ] **Step 2 : Lancer les tests → échec attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'service'`

- [ ] **Step 3 : Créer `service.py` (imports, helpers, `list_gpu_models`)**

```python
"""Logique pure du serveur MCP gpu-price (sans dépendance MCP).

Chaque fonction reçoit un :class:`~core.storage.protocols.PriceStore` injecté et renvoie un
dict/list JSON-sérialisable. Le point-in-time passe par ``as_of`` (ISO 8601 UTC, naïf rejeté).
Les prix servis sont **réels** (spot observé) : chaque réponse porte ``provenance="real"``.
"""
from __future__ import annotations

import datetime as dt
import statistics
from typing import Any

import pandas as pd

from core.storage import query as duckdb_query
from core.storage.parquet_store import ParquetPriceStore
from core.storage.protocols import PriceStore

#: Étiquette réel/simulé (règle forward-real-simulated.md) — ce serveur ne sert que du réel.
PROVENANCE = "real"


def _parse_instant(value: str | None) -> dt.datetime | None:
    """Parse un instant ISO 8601 en datetime UTC tz-aware ; ``None`` reste ``None``.

    Raises
    ------
    ValueError
        Si ``value`` n'est pas un ISO 8601 valide, ou s'il est naïf (sans fuseau).
    """
    if value is None:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Instant ISO 8601 invalide : {value!r}. Exemple : '2026-06-21T00:00:00+00:00'."
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"Instant naïf interdit : {value!r}. Fournir un instant tz-aware UTC "
            "(ex. '2026-06-21T00:00:00+00:00')."
        )
    return parsed.astimezone(dt.timezone.utc)


def list_gpu_models(store: PriceStore, *, as_of: str | None = None) -> list[str]:
    """Liste triée des modèles GPU présents dans le lac (bornée à ``snapshotted_at <= as_of``)."""
    frame = store.read(as_of=_parse_instant(as_of))
    if frame.empty:
        return []
    return sorted(frame["gpu_model"].unique().tolist())
```

- [ ] **Step 4 : Lancer les tests → succès attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v`
Expected: PASS (5 tests : `list_gpu_models`, point-in-time, naïf, ISO invalide, store vide)

- [ ] **Step 5 : Commit**

```bash
git add infra/mcp-servers/gpu-price-server/service.py \
        infra/mcp-servers/gpu-price-server/tests/test_service.py
git commit -m "feat(gpu-price): list_gpu_models + parse as_of point-in-time (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 : `latest_price` (TDD)

**Files:**
- Modify: `infra/mcp-servers/gpu-price-server/service.py`
- Modify: `infra/mcp-servers/gpu-price-server/tests/test_service.py`

- [ ] **Step 1 : Ajouter les tests qui échouent** (à la fin de `test_service.py`)

```python
def test_latest_price_freshest_per_source_cheapest(store):
    res = latest_price(store, "H100")
    assert res["found"] is True
    assert res["provenance"] == "real"
    by = {d["source"]: d["price_usd_per_hour"] for d in res["by_source"]}
    # vastai : instant le plus récent = T1, offre la moins chère = 1.80 ; runpod T1 = 2.10
    assert by == {"vastai": 1.80, "runpod": 2.10}
    assert res["summary"] == {"min": 1.80, "median": 1.95, "max": 2.10, "n_sources": 2}


def test_latest_price_point_in_time(store):
    res = latest_price(store, "H100", as_of=T0.isoformat())
    by = {d["source"]: d["price_usd_per_hour"] for d in res["by_source"]}
    # à T0 les relevés T1 sont exclus → anti look-ahead
    assert by == {"vastai": 2.00, "runpod": 2.20}


def test_latest_price_unknown_model(store):
    res = latest_price(store, "RTX9999")
    assert res["found"] is False
    assert "RTX9999" in res["message"]
    assert "H100" in res["available_models"]
```

- [ ] **Step 2 : Lancer → échec attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k latest_price`
Expected: FAIL — `AttributeError`/`ImportError` (`latest_price` pas encore défini dans service)

- [ ] **Step 3 : Ajouter `_latest_row_per_source` + `latest_price` à `service.py`**

```python
def _latest_row_per_source(subset: pd.DataFrame) -> pd.DataFrame:
    """Par source : l'instant le plus récent, puis l'offre la moins chère à cet instant."""
    freshest_per_source = subset.groupby("source")["snapshotted_at"].transform("max")
    freshest = subset[subset["snapshotted_at"] == freshest_per_source]
    cheapest_idx = freshest.groupby("source")["price_usd_per_hour"].idxmin()
    return freshest.loc[cheapest_idx].sort_values("source")


def latest_price(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str = "on_demand",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Dernier prix par source pour ``gpu_model``/``lease_type`` (réel) + résumé min/médian/max."""
    frame = store.read(as_of=_parse_instant(as_of))
    subset = frame[(frame["gpu_model"] == gpu_model) & (frame["lease_type"] == lease_type)]
    if subset.empty:
        available = sorted(frame["gpu_model"].unique().tolist()) if not frame.empty else []
        return {
            "gpu_model": gpu_model,
            "lease_type": lease_type,
            "found": False,
            "provenance": PROVENANCE,
            "message": f"Aucun relevé pour gpu_model={gpu_model!r}, lease_type={lease_type!r}.",
            "available_models": available,
        }
    latest = _latest_row_per_source(subset)
    by_source = [
        {
            "source": row.source,
            "price_usd_per_hour": float(row.price_usd_per_hour),
            "availability": int(row.availability),
            "snapshotted_at": row.snapshotted_at.isoformat(),
        }
        for row in latest.itertuples(index=False)
    ]
    prices = [item["price_usd_per_hour"] for item in by_source]
    return {
        "gpu_model": gpu_model,
        "lease_type": lease_type,
        "found": True,
        "provenance": PROVENANCE,
        "as_of": subset["snapshotted_at"].max().isoformat(),
        "by_source": by_source,
        "summary": {
            "min": min(prices),
            "median": statistics.median(prices),
            "max": max(prices),
            "n_sources": len(prices),
        },
    }
```

- [ ] **Step 4 : Lancer → succès attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k latest_price`
Expected: PASS (3 tests)

- [ ] **Step 5 : Commit**

```bash
git add infra/mcp-servers/gpu-price-server/service.py \
        infra/mcp-servers/gpu-price-server/tests/test_service.py
git commit -m "feat(gpu-price): latest_price par source (freshest+cheapest, point-in-time) (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 : `price_history` (TDD)

**Files:**
- Modify: `infra/mcp-servers/gpu-price-server/service.py`
- Modify: `infra/mcp-servers/gpu-price-server/tests/test_service.py`

- [ ] **Step 1 : Ajouter les tests qui échouent**

```python
def test_price_history_ordered_and_source_filter(store):
    res = price_history(store, "H100", source="vastai")
    assert res["n"] == 3  # vastai H100 : T0(2.00), T1(1.80), T1(1.90)
    times = [o["snapshotted_at"] for o in res["observations"]]
    assert times == sorted(times)  # ordre croissant
    assert all(o["source"] == "vastai" for o in res["observations"])


def test_price_history_as_of_excludes_future(store):
    res = price_history(store, "H100", source="vastai", as_of=T0.isoformat())
    assert res["n"] == 1
    assert res["observations"][0]["price_usd_per_hour"] == 2.00


def test_price_history_start_bound(store):
    res = price_history(store, "H100", source="vastai", start=T1.isoformat())
    assert res["n"] == 2
    assert {o["price_usd_per_hour"] for o in res["observations"]} == {1.80, 1.90}
```

Et ajouter `T1` à l'import en tête de fichier :

```python
from conftest import T0, T1
```

- [ ] **Step 2 : Lancer → échec attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k price_history`
Expected: FAIL — `price_history` pas encore défini

- [ ] **Step 3 : Ajouter `price_history` à `service.py`**

```python
def price_history(
    store: PriceStore,
    gpu_model: str,
    *,
    start: str | None = None,
    as_of: str | None = None,
    source: str | None = None,
    lease_type: str | None = None,
) -> dict[str, Any]:
    """Série temporelle ordonnée des relevés (réel) de ``gpu_model`` dans ``[start, as_of]``."""
    cutoff = _parse_instant(as_of)
    start_dt = _parse_instant(start)
    frame = store.read(as_of=cutoff, source=source)
    subset = frame[frame["gpu_model"] == gpu_model]
    if lease_type is not None:
        subset = subset[subset["lease_type"] == lease_type]
    if start_dt is not None:
        subset = subset[subset["snapshotted_at"] >= pd.Timestamp(start_dt)]
    subset = subset.sort_values("snapshotted_at")
    observations = [
        {
            "snapshotted_at": row.snapshotted_at.isoformat(),
            "source": row.source,
            "lease_type": row.lease_type,
            "price_usd_per_hour": float(row.price_usd_per_hour),
            "availability": int(row.availability),
        }
        for row in subset.itertuples(index=False)
    ]
    return {
        "gpu_model": gpu_model,
        "start": start_dt.isoformat() if start_dt is not None else None,
        "as_of": cutoff.isoformat() if cutoff is not None else None,
        "provenance": PROVENANCE,
        "n": len(observations),
        "observations": observations,
    }
```

- [ ] **Step 4 : Lancer → succès attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k price_history`
Expected: PASS (3 tests)

- [ ] **Step 5 : Commit**

```bash
git add infra/mcp-servers/gpu-price-server/service.py \
        infra/mcp-servers/gpu-price-server/tests/test_service.py
git commit -m "feat(gpu-price): price_history (bornes start/as_of, filtres source/bail) (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5 : `summary_stats` (TDD)

**Files:**
- Modify: `infra/mcp-servers/gpu-price-server/service.py`
- Modify: `infra/mcp-servers/gpu-price-server/tests/test_service.py`

- [ ] **Step 1 : Ajouter les tests qui échouent**

```python
def test_summary_stats_overall_and_by_source(store):
    res = summary_stats(store, "H100")
    # prix H100 : 2.00, 2.20, 1.80, 1.90, 2.10  → 5 obs, mean 2.00, median 2.00
    assert res["n"] == 5
    overall = res["overall"]
    assert overall["count"] == 5
    assert overall["min"] == 1.80
    assert overall["max"] == 2.20
    assert overall["median"] == 2.00
    assert round(overall["mean"], 6) == 2.00
    by = {d["source"]: d["count"] for d in res["by_source"]}
    assert by == {"runpod": 2, "vastai": 3}


def test_summary_stats_as_of(store):
    res = summary_stats(store, "H100", as_of=T0.isoformat())
    assert res["n"] == 2  # T0 seulement : 2.00 (vastai), 2.20 (runpod)
    assert res["overall"]["min"] == 2.00
    assert res["overall"]["max"] == 2.20


def test_summary_stats_unknown_model(store):
    res = summary_stats(store, "RTX9999")
    assert res["found"] is False
    assert res["n"] == 0
```

- [ ] **Step 2 : Lancer → échec attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k summary_stats`
Expected: FAIL — `summary_stats` pas encore défini

- [ ] **Step 3 : Ajouter `summary_stats` à `service.py`**

```python
def summary_stats(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Stats descriptives (réel) des prix de ``gpu_model``, bornées au point-in-time ``as_of``."""
    cutoff = _parse_instant(as_of)
    frame = store.read(as_of=cutoff)
    subset = frame[frame["gpu_model"] == gpu_model]
    if lease_type is not None:
        subset = subset[subset["lease_type"] == lease_type]
    if subset.empty:
        return {
            "gpu_model": gpu_model,
            "found": False,
            "provenance": PROVENANCE,
            "n": 0,
            "message": f"Aucun relevé pour gpu_model={gpu_model!r}.",
        }
    prices = subset["price_usd_per_hour"]
    overall = {
        "count": int(prices.count()),
        "min": float(prices.min()),
        "max": float(prices.max()),
        "mean": float(prices.mean()),
        "median": float(prices.median()),
        "std": float(prices.std(ddof=0)),  # population : défini même pour n=1
    }
    by_source = [
        {
            "source": str(src),
            "count": int(grp["price_usd_per_hour"].count()),
            "min": float(grp["price_usd_per_hour"].min()),
            "max": float(grp["price_usd_per_hour"].max()),
            "mean": float(grp["price_usd_per_hour"].mean()),
            "median": float(grp["price_usd_per_hour"].median()),
        }
        for src, grp in subset.groupby("source")
    ]
    return {
        "gpu_model": gpu_model,
        "found": True,
        "provenance": PROVENANCE,
        "as_of": cutoff.isoformat() if cutoff is not None else subset["snapshotted_at"].max().isoformat(),
        "n": int(prices.count()),
        "overall": overall,
        "by_source": sorted(by_source, key=lambda d: d["source"]),
        "first_obs_at": subset["snapshotted_at"].min().isoformat(),
        "last_obs_at": subset["snapshotted_at"].max().isoformat(),
    }
```

- [ ] **Step 4 : Lancer → succès attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k summary_stats`
Expected: PASS (3 tests)

- [ ] **Step 5 : Commit**

```bash
git add infra/mcp-servers/gpu-price-server/service.py \
        infra/mcp-servers/gpu-price-server/tests/test_service.py
git commit -m "feat(gpu-price): summary_stats (overall + par source, point-in-time) (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6 : `run_query` (SQL DuckDB brut) (TDD)

**Files:**
- Modify: `infra/mcp-servers/gpu-price-server/service.py`
- Modify: `infra/mcp-servers/gpu-price-server/tests/test_service.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

```python
def test_run_query_counts_by_model(store):
    res = run_query(
        store, "SELECT gpu_model, count(*) AS n FROM prices GROUP BY gpu_model ORDER BY gpu_model"
    )
    assert "note" in res and "point-in-time" in res["note"]
    rows = {r["gpu_model"]: r["n"] for r in res["rows"]}
    assert rows == {"A100": 1, "B200": 1, "H100": 5}
    assert res["columns"] == ["gpu_model", "n"]
```

- [ ] **Step 2 : Lancer → échec attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v -k run_query`
Expected: FAIL — `run_query` pas encore défini

- [ ] **Step 3 : Ajouter `_jsonable` + `run_query` à `service.py`**

```python
def _jsonable(value: Any) -> Any:
    """Rend une valeur DuckDB/pandas sérialisable JSON (Timestamp→ISO, NaN→None, numpy→python)."""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):  # scalaires numpy
        return value.item()
    return value


def run_query(store: ParquetPriceStore, sql: str) -> dict[str, Any]:
    """Exécute ``sql`` (DuckDB **brut**) sur la vue ``prices`` du lac. Aucun garde point-in-time."""
    frame = duckdb_query(sql, store)
    rows = [{k: _jsonable(v) for k, v in record.items()} for record in frame.to_dict(orient="records")]
    return {
        "columns": list(frame.columns),
        "rows": rows,
        "n": len(rows),
        "note": "SQL DuckDB brut — AUCUN garde point-in-time ; le filtrage as_of est à la charge de la requête.",
    }
```

- [ ] **Step 4 : Lancer → succès attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_service.py -v`
Expected: PASS (toute la suite service, ~15 tests)

- [ ] **Step 5 : Commit**

```bash
git add infra/mcp-servers/gpu-price-server/service.py \
        infra/mcp-servers/gpu-price-server/tests/test_service.py
git commit -m "feat(gpu-price): query SQL DuckDB brut (delegation core.storage.query) (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7 : `server.py` (câblage FastMCP) + smoke test (TDD)

**Files:**
- Create: `infra/mcp-servers/gpu-price-server/server.py`
- Create: `infra/mcp-servers/gpu-price-server/tests/test_server.py`

- [ ] **Step 1 : Écrire le smoke test qui échoue**

Créer `tests/test_server.py` :

```python
"""Smoke test : le serveur enregistre bien les 5 outils MCP."""
from __future__ import annotations

import asyncio


def test_server_registers_five_tools():
    import server

    tools = asyncio.run(server.mcp.list_tools())
    names = sorted(t.name for t in tools)
    assert names == ["latest_price", "list_gpu_models", "price_history", "query", "summary_stats"]
```

- [ ] **Step 2 : Lancer → échec attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3 : Créer `server.py`**

```python
"""Serveur MCP `gpu-price` — expose les snapshots de prix GPU (réel) via FastMCP/stdio.

Câblage seulement : chaque outil délègue à une fonction pure de ``service``. La racine du lac
est résolue via ``$CLAUDE_PROJECT_DIR`` (Claude Code) ou en remontant depuis ce fichier.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import service
from core.storage import ParquetPriceStore


def _snapshot_root() -> Path:
    """Racine du lac Parquet : ``$CLAUDE_PROJECT_DIR/data/snapshots`` ou résolution relative."""
    base = os.environ.get("CLAUDE_PROJECT_DIR")
    root = Path(base) if base else Path(__file__).resolve().parents[3]
    return root / "data" / "snapshots"


_STORE = ParquetPriceStore(_snapshot_root())
mcp = FastMCP("gpu-price")


@mcp.tool()
def list_gpu_models(as_of: str | None = None) -> list[str]:
    """Modèles GPU connus (réel), triés, bornés au point-in-time ``as_of`` (ISO 8601 UTC)."""
    return service.list_gpu_models(_STORE, as_of=as_of)


@mcp.tool()
def latest_price(
    gpu_model: str, lease_type: str = "on_demand", as_of: str | None = None
) -> dict[str, Any]:
    """Dernier prix observé par source pour ``gpu_model`` (réel) + résumé min/médian/max."""
    return service.latest_price(_STORE, gpu_model, lease_type=lease_type, as_of=as_of)


@mcp.tool()
def price_history(
    gpu_model: str,
    start: str | None = None,
    as_of: str | None = None,
    source: str | None = None,
    lease_type: str | None = None,
) -> dict[str, Any]:
    """Série temporelle des relevés (réel) de ``gpu_model`` dans ``[start, as_of]``."""
    return service.price_history(
        _STORE, gpu_model, start=start, as_of=as_of, source=source, lease_type=lease_type
    )


@mcp.tool()
def summary_stats(
    gpu_model: str, lease_type: str | None = None, as_of: str | None = None
) -> dict[str, Any]:
    """Stats descriptives (réel) des prix de ``gpu_model``, bornées au point-in-time."""
    return service.summary_stats(_STORE, gpu_model, lease_type=lease_type, as_of=as_of)


@mcp.tool()
def query(sql: str) -> dict[str, Any]:
    """SQL DuckDB **brut** sur la vue ``prices`` (le lac). ⚠️ Full DuckDB, aucun garde point-in-time."""
    return service.run_query(_STORE, sql)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4 : Lancer → succès attendu**

Run: `pytest infra/mcp-servers/gpu-price-server/tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add infra/mcp-servers/gpu-price-server/server.py \
        infra/mcp-servers/gpu-price-server/tests/test_server.py
git commit -m "feat(gpu-price): server.py FastMCP/stdio (5 outils) + smoke test (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8 : Gate qualité + vérification bout-en-bout

**Files:** aucun nouveau fichier (vérification).

- [ ] **Step 1 : Suite complète verte**

Run: `pytest infra/mcp-servers/gpu-price-server/tests -v`
Expected: PASS (logique + smoke, ~16 tests)

- [ ] **Step 2 : ruff propre**

Run: `ruff check infra/mcp-servers/gpu-price-server`
Expected: `All checks passed!` (sinon `ruff check --fix` puis `ruff format`, re-committer)

- [ ] **Step 3 : mypy propre sur la logique**

Run: `mypy infra/mcp-servers/gpu-price-server/service.py`
Expected: `Success` (la config repo est `ignore_missing_imports = true`)

- [ ] **Step 4 : Démarrage réel du serveur sur les vraies données**

Run (depuis la racine du repo) :
```bash
python -c "import sys; sys.path.insert(0, 'infra/mcp-servers/gpu-price-server'); \
import service; from core.storage import ParquetPriceStore; \
s = ParquetPriceStore('data/snapshots'); \
print('modèles:', service.list_gpu_models(s)[:8]); \
print('latest V100:', service.latest_price(s, 'V100'))"
```
Expected: une liste de modèles non vide + un `latest_price` cohérent issu de `data/snapshots/`
(provenance `real`). Si `found: false` pour `V100`, tester un modèle listé à l'étape précédente.

- [ ] **Step 5 : Test point-in-time bout-en-bout (preuve anti look-ahead)**

Déjà couvert par `test_latest_price_point_in_time` et `test_price_history_as_of_excludes_future` ;
confirmer leur présence verte :
Run: `pytest infra/mcp-servers/gpu-price-server/tests -v -k "point_in_time or as_of_excludes"`
Expected: PASS

- [ ] **Step 6 : Finir — branche prête pour convergence**

Le code vit dans le module possédé ; `CONVERGENCE.md` liste les edits zone protégée à appliquer.
Ne PAS modifier `pyproject.toml`/`ci.yml` ici. Utiliser `superpowers:finishing-a-development-branch`
pour décider du devenir de `feat/gpu-price-mcp` (merge via `integration`, PR, etc.).

---

## Self-review (auteur)

- **Couverture spec :** `list_gpu_models`/`latest_price`/`price_history`/`summary_stats`/`query` → Tasks 2-6 ;
  point-in-time `as_of` partout + rejet naïf → Tasks 2-5 ; sécurité SQL documentée → Task 1 (README) + Task 6 ;
  provenance `real` → toutes réponses ; smoke 5 outils → Task 7 ; gate ruff/mypy + e2e → Task 8 ;
  handoff zone protégée → Task 1 (CONVERGENCE.md). ✅
- **Placeholders :** aucun — chaque step a son code/commande/sortie attendue.
- **Cohérence des types :** `_parse_instant`/`_latest_row_per_source`/`_jsonable` définis avant usage ;
  noms d'outils identiques entre `server.py` et le smoke test ; signatures `service` ↔ `server` alignées.
