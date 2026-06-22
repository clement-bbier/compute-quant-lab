"""Tests du référentiel d'efficacité GPU (Task A1, plan sprint pricing/énergie)."""

from __future__ import annotations

import pytest

from core.pricing.efficiency import GPU_SPECS, flops_per_watt, tflops_fp16


def test_known_specs_present() -> None:
    for gpu in ("A100", "H100", "H200", "B200"):
        assert gpu in GPU_SPECS


def test_flops_per_watt_h100() -> None:
    # H100 SXM : 989.5 TFLOPS FP16 Tensor dense @ 700 W -> ~1.414 TFLOPS/W
    assert flops_per_watt("H100") == pytest.approx(989.5 / 700.0, rel=1e-6)


def test_blackwell_more_efficient_than_hopper() -> None:
    assert flops_per_watt("B200") > flops_per_watt("H100") > flops_per_watt("A100")


def test_unknown_gpu_raises() -> None:
    with pytest.raises(KeyError):
        tflops_fp16("RTX_FANTASY")
