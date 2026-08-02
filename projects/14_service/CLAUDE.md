# Project 14 — `service_product`: the revenue vehicle

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md).

## Specific thesis
Turn the asset (multi-venue benchmark + procurement signal) into a **product people pay
for**: a dashboard/alerting system for "the cheapest GPU right now + price trend".
Public free tier = the **measurement**; premium = the **decision** (calibrated timing),
plugged into the private edge — never exposed in the clear.

## Owned modules
- `projects/14_service/` only.
- Read-only (consumption, never rewrite): `core.storage`, `core.ingestion`.
- Protected zone untouched (`CLAUDE.md` root, `.claude/`, `.mcp.json`, `pyproject.toml`, `core/`).

## Edge boundary (PUBLIC product — non-negotiable)
The product depends only on the `SignalSource` Protocol: the default public
implementation (`NaiveSignalSource`) is a trivial non-edge heuristic; a private edge
implementation substitutes it locally. Since nothing edge-specific is ever imported,
edge leakage is structurally impossible (guarded by `mypy` + an anti-import test,
`test_di_without_edge.py`).

## Real / point-in-time
Everything comes from the real, versioned cold store (`core.storage`). Index +
anti-look-ahead delegated to `core.ingestion.build_spot_index` (reuse, zero rewrite
of `core/`). Degrades gracefully when the lake is thin — no invented value.

## Progress status (PoC-now)
- [x] Public measurement (`views.py`) on the real cold store, point-in-time
- [x] `SignalSource` boundary + default naive public impl (non-edge, `simulated=True`)
- [x] Alert skeleton (single injection point, declarative rules, stub notifier)
- [x] Streamlit dashboard (cheapest + dispersion + trend + methodology, graceful degradation)
- [x] 36 tests passing; no edge in the clear
- [ ] Convergence: `pyproject` testpaths `projects/14…/tests` (protected zone, out of scope)

## Launch
```bash
uv run pytest projects/14_service/tests
uv run streamlit run projects/14_service/dashboard/app.py
```
