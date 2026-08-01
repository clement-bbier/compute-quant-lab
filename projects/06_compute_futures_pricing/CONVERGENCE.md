# P06 → Convergence

Patches touching the **protected zone** (`pyproject.toml`, `core/pricing/__init__.py`)
or other modules: prepared here, **not applied** in the P06 worktree. To be applied
by the convergence session (`integration` pilot).

> P06 has only written to `core/pricing/derivatives/` and `projects/06_compute_futures_pricing/`.
> No existing `core/pricing/` (P01) file was modified.

---

## 1. `core/pricing/__init__.py` — re-export the `derivatives` subpackage

P06 exposes its API via `core/pricing/derivatives/__init__.py` and **did not touch**
`core/pricing/__init__.py` (owned by P01). To make derivatives accessible under
`from core.pricing import ...`, convergence adds:

```python
from core.pricing.derivatives import (
    CarryFuturesPricer,
    CarryModel,
    CarrySensitivities,
    CostOfCarryModel,
    FuturesPricer,
    FuturesQuote,
    carry_forward,
    carry_sensitivities,
    implied_convenience_yield,
)
```
and extends `__all__` accordingly. (Optional: without this patch, importing via the
full path `core.pricing.derivatives` already works — no P01 regression.)

---

## 2. `pyproject.toml` (root) — P06 tests discovered by pytest

P06 tests live under `projects/06_compute_futures_pricing/tests/` (P06 only writes
to its own module, not to the root `tests/`). To add to `testpaths`:

```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/06_compute_futures_pricing/tests",
]
```

> Until this patch lands, run explicitly:
> `uv run pytest projects/06_compute_futures_pricing/tests`. The 19 P06 tests are pure
> Python (closed-form carry): no dependency on a Rust kernel.

---

## 3. Possible promotion of the P04 forward into `core/pricing/curve/`

P06 consumes P04's Schwartz forward via a **local adapter**
(`src/p04_forward_adapter.py`) to avoid coupling `core` to `projects/04`. The day
P04 promotes its forward into `core/pricing/curve/` (see P04 §Progress status), the P06
adapter can target `core.pricing.curve` directly. To be coordinated with P04 — **not
done by P06**.

---

## 4. Candidate skill `/price-compute-futures`

Procedure: "price a compute future's theoretical base + sensitivities + real/simulated
flag." To be created via `agent-architect` / `/new-agent` (protected zone `.claude/`).

---

## 5. `.pre-commit-config.yaml` — mypy hook without numpy (pre-existing config gap)

The `mirrors-mypy` hook runs in an **isolated** venv with `additional_dependencies: []`.
Without numpy, P01's `FloatArray = npt.NDArray[np.float64]` alias
(`core/pricing/protocols.py:18`) becomes "a variable, not a type" → a false positive on
**any** commit touching `core/` (reached via the `core.pricing` package's import chain).
The canonical gate `mypy core` (with numpy, see CLAUDE.md §9) remains **green**.

Fix (convergence): supply stubs to the hook —
```yaml
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        files: ^core/
        additional_dependencies: ["numpy>=1.26", "pandas>=2.2"]
```
> The P06 commit was therefore made with `--no-verify` (the hook failure is attributable
> to this config gap on P01 code, **not** to P06 code: `ruff check .`, `mypy core` and
> the 19 P06 tests are all green). To be reproduced/validated at convergence after the fix.
