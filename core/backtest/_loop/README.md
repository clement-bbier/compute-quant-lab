# `backtest_loop` — Rust kernel (phase 2)

**Standalone maturin subcrate**: point-in-time PnL accumulation loop, the phase 2
**fast path** of the engine. Replicates bit-for-bit the Python oracle
`core/backtest/reference_loop.py` (parity tested by `test_parity`).

## Build (optional — the kernel is a fast path, not a requirement)

```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
```

Installs the compiled `backtest_loop` module into the venv. `core.backtest.engine`
imports it when present and otherwise falls back to the Python oracle, logging a
warning: `import core.backtest` therefore works on a machine without a Rust
toolchain, and results are identical either way — only throughput differs. The
active implementation is exposed as `core.backtest.engine.USING_RUST_KERNEL`, and
the Rust-only tests skip when the crate is absent (same policy as the P01 pricing
kernel).

> ⚠️ Wiring this build into the root `pyproject.toml` plus the Rust CI remains an
> open gap — see `docs/decisions/002-per-project-ci-testpaths-gap.md`.
