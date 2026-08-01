"""Executable entry point: measures the inter-region energy ↔ compute basis and logs it.

Usage:
    uv run python projects/05_energy_compute_basis/src/run_basis.py

Pipeline: (1) FR/DE regional energy (real ENTSO-E if token set, else labeled synthetic
fallback) + P04 global compute index; (2) one ``SparkSpreadPricer`` (P01) per region
carrying its PUE; (3) point-in-time ``BasisCalculator``; (4) ``detect_dislocations``
(threshold + AR(1) half-life); (5) logged **MLflow run** (params + git SHA); (6)
``results/SYNTHESIS.md`` synthesis.

Real/synthetic boundary: ``energy_source`` / ``compute_source`` are logged as params.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Lab convention: local file-based MLflow tracking. MLflow 2026 requires this opt-in.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("MLFLOW_TRACKING_URI", (_ROOT / "experiments" / "mlruns").as_uri())
sys.path.insert(0, str(Path(__file__).resolve().parent))  # makes `basis`, `data`… importable

import mlflow  # noqa: E402

from basis import BasisCalculator, BasisResult, DislocationSummary, detect_dislocations  # noqa: E402
from core.pricing import DataFramePriceSource  # noqa: E402
from core.utils.tracking import run as mlflow_run  # noqa: E402
from data import hourly_index, load_compute_index, load_regional_energy  # noqa: E402
from region_config import DEFAULT_REGIONS, RegionConfig, build_regional_pricer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("run_basis")

EXPERIMENT = "p05_energy_compute_basis"
GPU = "H100"
REFERENCE = "DE"
WINDOW_START = "2025-01-01"
DEFAULT_PERIODS = 31 * 24  # one hourly month
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def build_source(
    index, regions: tuple[RegionConfig, ...], *, allow_remote: bool
) -> tuple[DataFramePriceSource, str, str]:
    """Loads energy + compute and assembles the P01 price source (+ source labels)."""
    energy_df, energy_source = load_regional_energy(
        index, [r.code for r in regions], allow_remote=allow_remote
    )
    compute_df, compute_source = load_compute_index(index, GPU)
    source = DataFramePriceSource(energy=energy_df, compute=compute_df)
    return source, energy_source, compute_source


def analyse(
    source: DataFramePriceSource, regions: tuple[RegionConfig, ...], reference: str, gpu: str
) -> tuple[BasisResult, dict[str, DislocationSummary]]:
    """Prices each region and computes basis + dislocations (per region ≠ reference)."""
    pricers = {r.code: build_regional_pricer(r) for r in regions}
    result = BasisCalculator(pricers, reference=reference).compute(source, gpu)
    dislocations = {region: detect_dislocations(series) for region, series in result.basis.items()}
    return result, dislocations


def _params(
    regions: tuple[RegionConfig, ...],
    reference: str,
    gpu: str,
    result: BasisResult,
    energy_source: str,
    compute_source: str,
) -> dict[str, object]:
    params: dict[str, object] = {
        "gpu": gpu,
        "reference": reference,
        "regions": ",".join(r.code for r in regions),
        "energy_source": energy_source,
        "compute_source": compute_source,
        "fx_eur_per_usd": regions[0].fx_eur_per_usd,
        "window_start": str(result.window[0]),
        "window_end": str(result.window[1]),
    }
    for region in regions:
        params[f"pue_{region.code}"] = region.pue
        params[f"tdp_w_{region.code}"] = region.tdp_w
    return params


def _metrics(result: BasisResult, dislocations: dict[str, DislocationSummary]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for region, series in result.basis.items():
        summary = dislocations[region]
        metrics[f"basis_{region}_mean"] = float(series.mean())
        metrics[f"basis_{region}_std"] = float(series.std())
        metrics[f"amplitude_p95_{region}"] = summary.amplitude_p95
        metrics[f"fraction_dislocated_{region}"] = summary.fraction_dislocated
        metrics[f"n_dislocations_{region}"] = float(summary.n_dislocations)
        if summary.half_life_hours is not None:
            metrics[f"half_life_hours_{region}"] = summary.half_life_hours
    return metrics


def write_synthesis(
    results_dir: Path,
    regions: tuple[RegionConfig, ...],
    reference: str,
    result: BasisResult,
    dislocations: dict[str, DislocationSummary],
    energy_source: str,
    compute_source: str,
) -> Path:
    """Writes ``results/SYNTHESIS.md``: basis amplitude, PUE sensitivity, limitations."""
    results_dir.mkdir(parents=True, exist_ok=True)
    pue_map = ", ".join(f"{r.code}={r.pue}" for r in regions)
    lines = [
        "# P05 — Energy ↔ compute basis synthesis",
        "",
        f"- Regions: {', '.join(r.code for r in regions)} (reference = {reference})",
        f"- Window: {result.window[0]} → {result.window[1]} (UTC)",
        f"- Sources: energy = **{energy_source}**, compute = **{compute_source}** (GLOBAL compute)",
        f"- Regional PUE (assumption): {pue_map}",
        "",
        "## Basis amplitude & persistence",
        "",
        "| basis | mean (€/GPU·h) | std dev | p95 amplitude | % time dislocated | episodes | half-life (h) |",
        "|---|---|---|---|---|---|---|",
    ]
    for region, series in result.basis.items():
        summary = dislocations[region]
        half_life = "n/a" if summary.half_life_hours is None else f"{summary.half_life_hours:.2f}"
        lines.append(
            f"| {region}−{reference} | {series.mean():.5f} | {series.std():.5f} | "
            f"{summary.amplitude_p95:.5f} | {summary.fraction_dislocated:.1%} | "
            f"{summary.n_dislocations} | {half_life} |"
        )
    lines += [
        "",
        "## PUE sensitivity",
        "",
        "At equal FX and compute price, the basis is driven by `power_kw·(pue_r·energy_r − "
        "pue_ref·energy_ref)/1000`: ↑ a region's PUE ⇒ ↑ its cost ⇒ ↓ its spread ⇒ ↓ its "
        "basis. Sensitivity is tested (`test_pue_sensitivity_is_monotone`).",
        "",
        "## Execution limitations (PoC)",
        "",
        "- **Regional PUE** = a strong, poorly observable assumption; the main driver of the basis here.",
        "- **Global compute** (a single curve): revenue cancels out between regions → the basis "
        "is essentially an *energy × PUE basis*, not a true regional compute spread.",
        "- **Transfer costs/latency ignored**: do not conclude this is an executable arbitrage.",
        "- Institutional next steps: optimized routing, capacity constraints, tradable signal.",
        "",
    ]
    path = results_dir / "SYNTHESIS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(
    *,
    results_dir: Path = RESULTS_DIR,
    periods: int = DEFAULT_PERIODS,
    allow_remote: bool = True,
    experiment: str = EXPERIMENT,
) -> tuple[BasisResult, dict[str, DislocationSummary]]:
    """Orchestrates the full pipeline and logs a reproducible MLflow run."""
    regions = DEFAULT_REGIONS
    index = hourly_index(WINDOW_START, periods)

    source, energy_source, compute_source = build_source(index, regions, allow_remote=allow_remote)
    result, dislocations = analyse(source, regions, REFERENCE, GPU)

    params = _params(regions, REFERENCE, GPU, result, energy_source, compute_source)
    metrics = _metrics(result, dislocations)
    with mlflow_run(experiment, params):
        for key, value in metrics.items():
            mlflow.log_metric(key, value)

    path = write_synthesis(
        results_dir, regions, REFERENCE, result, dislocations, energy_source, compute_source
    )

    for region, summary in dislocations.items():
        half_life = "n/a" if summary.half_life_hours is None else f"{summary.half_life_hours:.2f} h"
        log.info(
            "basis %s−%s: mean=%.5f, p95=%.5f, dislocated=%.1f%%, half-life=%s",
            region,
            REFERENCE,
            result.basis[region].mean(),
            summary.amplitude_p95,
            summary.fraction_dislocated * 100,
            half_life,
        )
    log.info("Synthesis written: %s | run logged (experiment '%s').", path, experiment)
    return result, dislocations


if __name__ == "__main__":
    main()
