# `core/signals/` — reusable signal producers

**PoC → foundation** promotion (P12): signal logic from research projects moves up here
behind a common `SignalProducer` Protocol, so the P10 desk (and any future consumer)
depends on an abstraction, never on a concrete implementation.

## Contract (`protocols.py`)
- `SignalProducer.signal(view: PointInTimeView) -> float` — a normalised directional
  view in `[-1, 1]`, computed point-in-time (never a final position; sizing is the
  desk's job).
- `signal(view)` is exactly the `Strategy` Protocol signature from `core.backtest`, so
  every producer here is directly backtestable by the P08 engine.
- `SignalProvenance(name, simulated)` — `simulated` is mandatory (no default), per the
  `forward-real-simulated` rule.

## Producers
| Module | Signal | Promoted from |
|---|---|---|
| `mean_reversion.py` | `MeanReversionSignal` — spread mean reversion (hysteresis z-score) | P02 |
| `futures_basis.py` | `FuturesBasisSignal` — carry/roll of the future/spot basis | P06 |
| `ml.py` | `MLEnsembleSignal` — out-of-sample ML directional signal (wraps the P09 adapter) | P09 |

## Tests
```bash
uv run pytest core/signals/tests   # 23 passed
```
Point-in-time integrity is proven by invariance to future falsification (a producer's
output at `t` cannot change when rows after `t` are added).

## Consumers
`projects/10_portfolio_execution/` wires all three producers into the desk via
`REAL_PRODUCERS`, replacing the earlier in-memory mocks — see
[`projects/10_portfolio_execution/CLAUDE.md`](../../projects/10_portfolio_execution/CLAUDE.md).
