# `private/` — edge zone, NEVER versioned online

> The repo is **public**. Anything that constitutes a **monetizable edge**
> (signals that make money, winning calibrated parameters, real execution
> strategies) lives **here** and is **never** pushed. Only this `README.md`
> and `.gitkeep` are tracked.

## Rule (non-negotiable)
- The **public** side shows the **infrastructure** and the **benchmark**
  (impressive, sellable as portfolio / data) — **not the edge**.
- The **private** side keeps what wins: a signal committed to a public repo
  is **dead edge** (everyone can see it). This is the infra (public) /
  alpha (private) separation.

## Gitignored conventions (see `.gitignore`)
- All of `private/**` (except this README + `.gitkeep`).
- Any `*.private.py`, `*.private.json`, `*.private.parquet` file, **wherever it is**.

## What goes where
| Type | Location |
|---|---|
| Winning procurement signal, calibrated params | `private/procurement/` |
| Real tradable strategy, optimized thresholds | `private/strategies/` |
| Edge data/derivatives | `private/data/` or `*.private.parquet` |
| Generic reusable building block (no edge) | stays in `core/` (public) |

> When in doubt: "does seeing this file give someone an advantage I lose?"
> -> if yes, **private**.
