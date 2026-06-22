"""Orchestration du benchmark spot compute : cold store → indice + dispersion → MLflow + results/.

Lit le **cold store réel** versionné (Parquet, ``core.storage.ParquetSnapshotStore`` sur
``data/snapshots``), construit l'indice canonique quotidien + la dispersion inter-venues
via la couche pure ``benchmark``, logge un run MLflow reproductible (params + SHA + version
DVC, provenance ``real_spot``) et écrit une synthèse auditable dans ``results/``.

Granularité produit : **fix quotidien** (00:30 UTC). Le fix d'un jour settle après coup
(fenêtre de staleness 24 h) ; la grille s'étend donc de ``staleness`` au-delà du dernier
relevé pour inclure le fix de settlement le plus récent.

Données : ce worktree démarre avec ``data/snapshots`` vide. Pour un run réel, peupler le
lac via ``git checkout data-snapshots -- data/snapshots`` (ou ``dvc pull`` en ops normales).
Lancement : ``uv run python projects/13_compute_benchmark/run_build_benchmark.py [--root DIR]``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import mlflow
import pandas as pd

# Rend le paquet projet `benchmark` (sous src/) importable hors pytest.
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from benchmark.index_series import daily_fix_grid  # noqa: E402
from benchmark.report import BenchmarkReport, HistoryState, build_report, multi_venue_models  # noqa: E402
from core.ingestion.compute_index import DEFAULT_INDEX_CONFIG, IndexConfig  # noqa: E402
from core.ingestion.protocols import Snapshot  # noqa: E402
from core.storage import ParquetSnapshotStore  # noqa: E402
from core.utils import tracking  # noqa: E402
from core.utils.config import SNAPSHOTS_DIR  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402

_LOG = get_logger("p13.benchmark")
_RESULTS_DIR = Path(__file__).resolve().parent / "results"

#: Modèles « phares » publiés même en mono-venue (indice calculable, dispersion flaggée).
HEADLINE_MODELS = ("H100", "H200", "B200")


def select_models(
    snapshots: list[Snapshot], *, config: IndexConfig = DEFAULT_INDEX_CONFIG
) -> list[str]:
    """Modèles à publier : multi-venues (dispersion) ∪ modèles phares présents (indice seul)."""
    present = {s.gpu_model for s in snapshots}
    selected = set(multi_venue_models(snapshots)) | {m for m in HEADLINE_MODELS if m in present}
    return sorted(selected)


def build_grid(
    history: HistoryState, *, config: IndexConfig = DEFAULT_INDEX_CONFIG
) -> list[dt.datetime]:
    """Grille de fix quotidiens couvrant l'historique + la fenêtre de settlement (staleness)."""
    if history.first_at is None or history.last_at is None:
        return []
    return daily_fix_grid(history.first_at, history.last_at + config.staleness)


def report_to_frames(report: BenchmarkReport) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Sérialise le report en trois frames auditables : indice, dispersion, niveaux venues."""
    index_rows = (
        pd.concat([m.index.to_frame() for m in report.models], ignore_index=True)
        if report.models
        else pd.DataFrame()
    )
    dispersion_rows = pd.DataFrame(
        [
            {
                "as_of": d.as_of,
                "gpu_model": d.gpu_model,
                "n_venues": d.n_venues,
                "index_price": d.index_price,
                "spread_abs": d.spread_abs,
                "spread_pct": d.spread_pct,
                "cv": d.cv,
                "cheapest_venue": d.cheapest_venue,
                "dearest_venue": d.dearest_venue,
            }
            for m in report.models
            for d in m.dispersion
        ]
    )
    levels_rows = pd.DataFrame(
        [
            {
                "gpu_model": m.gpu_model,
                "source": lv.source,
                "mean_rate": lv.mean_rate,
                "mean_discount_vs_index": lv.mean_discount_vs_index,
                "n_fixes": lv.n_fixes,
            }
            for m in report.models
            for lv in m.venue_levels
        ]
    )
    return index_rows, dispersion_rows, levels_rows


def write_results(report: BenchmarkReport, out_dir: Path) -> Path:
    """Écrit la synthèse markdown + les CSV dans ``out_dir`` ; renvoie le markdown."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index_df, dispersion_df, levels_df = report_to_frames(report)
    index_df.to_csv(out_dir / "index_series.csv", index=False)
    dispersion_df.to_csv(out_dir / "dispersion.csv", index=False)
    levels_df.to_csv(out_dir / "venue_levels.csv", index=False)

    h = report.history
    spread = report.mean_spread_pct()
    lines = [
        "# Compute Spot Benchmark — synthèse du run",
        "",
        "Indice spot **réel** (provenance `real_spot`), point-in-time, UTC. Mesure publiée :",
        "prix de référence GPU-heure (fix quotidien canonique 00:30 UTC) + dispersion",
        "inter-venues descriptive. **Aucun signal de timing** (« louer sur X maintenant ») publié.",
        "",
        "## État de l'historique (honnête — il est maigre au début, il grossit)",
        f"- Relevés : **{h.n_snapshots}** · venues : **{h.n_venues}** ({', '.join(h.sources) or '—'})",
        f"- Instants distincts : **{h.n_distinct_timestamps}** · span : **{h.span_hours:.1f} h**",
        f"- Fenêtre : {h.first_at} → {h.last_at}",
        f"- Fix quotidiens calculés sur la grille : **{len(report.fix_times)}**",
        "",
        "## Agrégat",
        f"- Modèles publiés : **{len(report.models)}** ({', '.join(m.gpu_model for m in report.models) or '—'})",
        "- Spread % inter-venues moyen (fix définis) : "
        + (f"**{spread:.2%}**" if spread is not None else "**n/a** (aucune dispersion définie)"),
        "",
        "## Dernier fix par modèle",
        "",
        "| Modèle | Indice $/GPU·h | Venues | Spread % | Moins chère |",
        "|---|---|---|---|---|",
    ]
    for m in report.models:
        if not m.index.points:
            lines.append(f"| {m.gpu_model} | — (pas de fix) | — | — | — |")
            continue
        last = m.index.points[-1]
        d = m.dispersion[-1]
        spread_cell = f"{d.spread_pct:.2%}" if d.spread_pct is not None else "n/a (mono-venue)"
        cheapest = d.cheapest_venue or "—"
        lines.append(
            f"| {m.gpu_model} | {last.price_usd_per_hour:.4f} | {d.n_venues} "
            f"| {spread_cell} | {cheapest} |"
        )
    lines += [
        "",
        "## Niveaux moyens par venue (descriptif, fenêtre — PAS un signal de timing)",
        "",
        "| Modèle | Venue | Niveau moyen $/h | Escompte moyen vs indice |",
        "|---|---|---|---|",
    ]
    for m in report.models:
        for lv in m.venue_levels:
            lines.append(
                f"| {m.gpu_model} | {lv.source} | {lv.mean_rate:.4f} "
                f"| {lv.mean_discount_vs_index:+.2%} |"
            )
    summary = out_dir / "benchmark_summary.md"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def run(root: Path, *, config: IndexConfig = DEFAULT_INDEX_CONFIG) -> BenchmarkReport:
    """Construit et logge le benchmark depuis le cold store ``root``."""
    snapshots = ParquetSnapshotStore(root).load()
    _LOG.info("Cold store %s : %d relevés chargés.", root, len(snapshots))
    models = select_models(snapshots, config=config)
    from benchmark.report import summarize_history

    history = summarize_history(snapshots)
    grid = build_grid(history, config=config)
    report = build_report(snapshots, models, grid, config=config)

    params = {
        "method": config.method,
        "staleness_hours": config.staleness.total_seconds() / 3600.0,
        "lease_type": config.lease_type,
        "fix_frequency": "daily",
        "fix_time_utc": "00:30",
        "n_fix_times": len(grid),
        "models": ",".join(models) or "none",
        "window_start": str(history.first_at),
        "window_end": str(history.last_at),
    }
    with tracking.run("compute_benchmark", params):
        mlflow.set_tag("provenance", "real_spot")
        mlflow.log_metric("n_models", len(report.models))
        mlflow.log_metric("n_fix_times", len(grid))
        mlflow.log_metric("history_n_snapshots", history.n_snapshots)
        mlflow.log_metric("history_n_venues", history.n_venues)
        mlflow.log_metric("history_n_distinct_timestamps", history.n_distinct_timestamps)
        mlflow.log_metric("history_span_hours", history.span_hours)
        spread = report.mean_spread_pct()
        if spread is not None:
            mlflow.log_metric("mean_spread_pct", spread)
        summary = write_results(report, _RESULTS_DIR)
        mlflow.log_artifact(str(summary))
    _LOG.info("Benchmark écrit dans %s (modèles=%d, fix=%d).", _RESULTS_DIR, len(models), len(grid))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit le benchmark spot compute public.")
    parser.add_argument(
        "--root", type=Path, default=SNAPSHOTS_DIR, help="Racine du cold store Parquet."
    )
    args = parser.parse_args()
    report = run(args.root)
    if not report.history.n_snapshots:
        _LOG.warning(
            "Cold store vide : peupler via `git checkout data-snapshots -- data/snapshots` "
            "(ou `dvc pull`) avant de relancer pour un benchmark réel."
        )


if __name__ == "__main__":
    main()
