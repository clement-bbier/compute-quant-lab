"""Frozen GPU efficiency reference table (single convention: dense FP16 Tensor TFLOPS).

Documented, non-magic convention (python-quality rule): every figure comes from
vendor datasheets, in **dense** FP16 Tensor (no sparsity), with the nominal TDP of
the SXM module. Serves as the common denominator for comparing the spread across
GPUs (the "per effective TFLOP" unit of account of the pricing/energy sprint).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuSpec:
    """Efficiency spec of a GPU.

    Parameters
    ----------
    tflops_fp16
        **Dense** FP16 Tensor throughput (no sparsity), in TFLOPS.
    tdp_w
        Nominal power (TDP) of the module, in watts.
    """

    tflops_fp16: float
    tdp_w: float


# Sources: NVIDIA datasheets (SXM modules, dense FP16 Tensor). To be revised through a
# dedicated note if the precision convention changes.
GPU_SPECS: dict[str, GpuSpec] = {
    "A100": GpuSpec(tflops_fp16=312.0, tdp_w=400.0),
    "H100": GpuSpec(tflops_fp16=989.5, tdp_w=700.0),
    "H200": GpuSpec(tflops_fp16=989.5, tdp_w=700.0),  # same compute as H100, more memory
    "B200": GpuSpec(tflops_fp16=2250.0, tdp_w=1000.0),
}


def tflops_fp16(gpu: str) -> float:
    """Dense FP16 Tensor TFLOPS of the GPU (raises ``KeyError`` if unknown)."""
    return GPU_SPECS[gpu].tflops_fp16


def flops_per_watt(gpu: str) -> float:
    """TFLOPS per watt efficiency (nominal TDP), the energy-efficiency denominator."""
    spec = GPU_SPECS[gpu]
    return spec.tflops_fp16 / spec.tdp_w
