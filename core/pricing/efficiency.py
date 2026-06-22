"""Référentiel figé d'efficacité GPU (convention unique : TFLOPS FP16 Tensor dense).

Convention documentée et non magique (rule python-quality) : tout chiffre vient des
datasheets constructeur, en FP16 Tensor **dense** (sans sparsité), TDP nominal du
module SXM. Sert de dénominateur commun pour comparer le spread entre GPU
(unité de compte « par TFLOP effectif » du sprint pricing/énergie).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuSpec:
    """Spec d'efficacité d'un GPU.

    Parameters
    ----------
    tflops_fp16
        Débit FP16 Tensor **dense** (sans sparsité), en TFLOPS.
    tdp_w
        Puissance nominale (TDP) du module, en watts.
    """

    tflops_fp16: float
    tdp_w: float


# Sources : datasheets NVIDIA (modules SXM, FP16 Tensor dense). À réviser via une
# fiche dédiée si la convention de précision change.
GPU_SPECS: dict[str, GpuSpec] = {
    "A100": GpuSpec(tflops_fp16=312.0, tdp_w=400.0),
    "H100": GpuSpec(tflops_fp16=989.5, tdp_w=700.0),
    "H200": GpuSpec(tflops_fp16=989.5, tdp_w=700.0),  # même calcul que H100, plus de mémoire
    "B200": GpuSpec(tflops_fp16=2250.0, tdp_w=1000.0),
}


def tflops_fp16(gpu: str) -> float:
    """TFLOPS FP16 Tensor dense du GPU (lève ``KeyError`` si inconnu)."""
    return GPU_SPECS[gpu].tflops_fp16


def flops_per_watt(gpu: str) -> float:
    """Efficacité TFLOPS par watt (TDP nominal), dénominateur d'efficacité énergétique."""
    spec = GPU_SPECS[gpu]
    return spec.tflops_fp16 / spec.tdp_w
