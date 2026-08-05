# `private/` — local-only zone, never versioned online

> The repo is **public** by design: it shows the infrastructure, the
> benchmark, and the research — including negative results. Anything
> that would only make sense to keep proprietary (calibrated live
> parameters, deployment thresholds, execution details) would live
> **here** and is **never** pushed. Only this `README.md` and
> `.gitkeep` are tracked.

## Rule
- The **public** side is the research lab: methods, data, backtests,
  and honest results.
- The **private** side is reserved for live-deployment artifacts, if
  and when an experiment ever graduates to one. As of today, the
  published results speak for themselves — nothing here claims
  otherwise.

## Gitignored conventions (see `.gitignore`)
- All of `private/**` (except this README + `.gitkeep`).
- Any `*.private.py`, `*.private.json`, `*.private.parquet` file,
  wherever it is.

> Rule of thumb: configuration you would not want a counterparty to
> read belongs here.
