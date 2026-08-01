# P03 → Convergence handoff

Items touching the **protected zone** (off-limits to the peripheral worktree). To be
handled by the convergence session when merging `feature/P03-gpu_vol_term_structure` → `integration`.

## 1. `pyproject.toml` — `testpaths` (required)
`[tool.pytest.ini_options].testpaths` does not include `projects/03`. Add the entry so
CI picks up the P03 suite (as already done for P04):

```toml
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/03_gpu_vol_term_structure/tests",  # <- P03 addition
]
```

In the meantime: local gate via explicit path — `pytest -q projects/03_gpu_vol_term_structure`.

## 2. Possible promotion to `core/` (to be decided)
`VolEstimator` (Protocol) + `RealizedVol`/`EwmaVol` are **generic** (no compute
dependency): candidates for promotion to `core/features/volatility.py` (reusable by
P02/P05). Keep in `projects/03` until a second consumer is confirmed (PoC →
foundation). Decision = convergence.

## 3. `arch` dependency (GARCH) — NOT added
The institutional tier (GARCH) would require `arch` in `pyproject.toml` (protected zone).
Deliberately deferred (per the instruction to "avoid a new dependency without convergence");
the `VolEstimator` (Protocol) is ready to accommodate it without touching consumers.

## 4. Cross-project consumption of the P04 forward
`run_analysis.py` imports the P04 `forward` package via `sys.path` insertion of
`projects/04_compute_index_curve/src` (the tested logic itself stays pure and does not
depend on it). If the forward is promoted to `core/pricing/curve/` (P04 handoff), replace this
import with the `core` import — with no change to the analysis logic.
