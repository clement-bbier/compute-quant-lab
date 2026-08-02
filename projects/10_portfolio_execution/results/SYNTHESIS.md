# P10 — Desk backtest synthesis (PoC-now, **real signals** P12)

> MLflow run `cfcd48b6…` · `simulated=True` · seed 42 · 1500 steps (daily step, 252/yr).
> Signals: **`mean_reversion_p02`, `futures_basis_p06`, `ml_ensemble_p09`** — the **real**
> producers promoted into `core.signals` (mocks → real, P12). **Inverse-vol** weighting
> (lookback 60, floor 1e-4, gross cap 1.0). Execution: fees 10 bps + slippage 5 bps + impact κ=0.02.

## 1. What's validated (the actual PoC deliverable)
The **desk pipeline** now runs on the **3 real signals** without any change to its logic (OCP):
- producers promoted into `core.signals` behind `SignalProducer` (compatible with P08's `Strategy`);
- each producer is **point-in-time** (proven by invariance to future falsification, 23 tests in `core/signals`);
- `MLEnsembleSignal` is in **exact parity** with the P09 adapter; `FuturesBasisSignal` is genuinely wired to P06's cost-of-carry (a backwardation regime flips the sign of the signal);
- **net PnL = gross − costs** and **exact attribution** (Σ contributions = gross PnL);
- reproducible MLflow run (params + net/gross metrics + figure + git SHA).

## 2. Metrics (gross vs net)
| Metric | Gross | Net |
|---|---:|---:|
| Total PnL (capital=1) | +0.5057 | **−4.4654** |
| Sharpe (annualized) | +1.240 | **−7.118** |
| Max drawdown | −0.0409 | −4.4654 |
| Turnover | 455.0 | 455.0 |
| Hit ratio | 0.529 | 0.271 |
| Trades | — | 1479 |

**Reading**: the gross is **positive** (+0.51, Sharpe 1.24) — but on a **mean-reverting
synthetic** series, that's an artifact (the signals track the generating process), **not
alpha**. The **net collapses to −4.47**: with a turnover of 455, execution costs don't just
*quadruple* the loss, they **blow it up**. Desk verdict unchanged: judge on **net**.

## 3. "Mocks → real": what changes? (requested honesty)
| | Mocks (previous run) | **Real (this run)** |
|---|---:|---:|
| Gross PnL | −0.153 | **+0.506** |
| Net PnL | −0.541 | **−4.465** |
| Turnover | 86.5 | **455.0** |
| Gross hit ratio | 0.491 | 0.529 |

Two **non-intuitive** lessons:
1. **Gross improves** (−0.15 → +0.51): the real signals have a structure that matches the
   OU series (mean-reversion + directional ML) where the stateless mocks had no edge at all.
   Warning: this is exactly the **backtest-on-simulated** trap (see P02, non-credible Sharpe 7.70):
   a flattering gross on synthetic data **predicts nothing** about the real world.
2. **Net gets worse** (−0.54 → −4.47): the real signals **trade much more** (turnover ×5.3:
   flipping hysteresis, ML band crossings, basis momentum). A gross multiplied by
   ~3 but a turnover multiplied by ~5 ⇒ **costs win**. The §10 lesson ("execution
   is the PnL killer") is **reinforced**, not softened, by the move to real signals.

## 4. Contribution by signal (gross PnL)
| Signal | Contribution | Comment |
|---|---:|---|
| `mean_reversion_p02` | +0.2366 | carries the PnL (the OU series **is** mean-reverting by construction) |
| `ml_ensemble_p09` | +0.2253 | carries the PnL (learns the direction on the same artifact) |
| `futures_basis_p06` | +0.0437 | marginal (carry momentum, weak on a stationary series) |
| **Sum** | **+0.5057** | = total gross PnL (exact attribution, confirmed) |

Unlike the mocks (momentum was a **detractor**), all 3 real signals contribute **positively** to
the gross — but all on the same synthetic artifact. Inverse-vol weights by vol, not by edge:
a **correlation-aware risk-parity** (ERC seam) remains the right next step (signals are correlated here).

## 5. Sensitivity to impact cost κ
| κ | Net PnL | Net Sharpe | Total cost |
|---:|---:|---:|---:|
| 0.00 | −0.1768 | −0.425 | 0.683 |
| 0.01 | −2.3211 | −4.643 | 2.827 |
| 0.02 | −4.4654 | −7.118 | 4.971 |
| 0.05 | −10.8983 | −9.849 | 11.404 |
| 0.10 | −21.6199 | −10.887 | 22.126 |

Net PnL is **monotonically decreasing** in κ (tested). **Even at κ=0** (purely linear costs), the
net is **already negative** (−0.18): turnover alone (455) is enough to wipe out the +0.51 gross.
A high-turnover signal needs an edge **proportional to its turnover** — here it doesn't have one
(and either way the gross is a synthetic artifact).

## 6. Limitations (to be addressed at convergence / institutional tier)
- **Synthetic series**: no alpha claimed. The positive gross is an **artifact**, not a deployment signal.
- **ML probability is OOS but not strictly walk-forward causal** (design assumption inherited from P09): a future fold could train the model that predicts a past row. At runtime the guard is clean; the **construction** of the probability is not → a target for the `risk-validator`.
- **Inverse-vol ignores correlations** between real signals (which are correlated here) → ERC.
- **Turnover not controlled**: no turnover penalty or inter-signal netting → capacity/live execution.
- **A single regime**: no multi-regime testing nor an evolving GPU universe (survivorship).

## 7. Reproduce
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run pytest core/signals/tests projects/10_portfolio_execution/tests   # 65 green
uv run python projects/10_portfolio_execution/src/run_desk.py            # → results/last_run.json + mlruns/
```
