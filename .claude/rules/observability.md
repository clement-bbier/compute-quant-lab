---
paths:
  - "core/**"
  - "infra/**"
  - "projects/**"
---
# Observability (logging policy)

Central logger: `core.utils.logging`. `get_logger(name)` for every module; entry points
(runners, collectors, dashboards, the MCP server) call `configure_logging()` once, at
`if __name__ == "__main__"` / module top for Streamlit apps. Library code (`core/`,
project `src/`) never calls `configure_logging` — only `get_logger`.

## Levels — what goes where

- **DEBUG**: values useful only while actively diagnosing (intermediate computation,
  request/response bodies once sanitized, cache hits/misses). Off by default.
- **INFO**: a boundary was crossed successfully — a file was read/written, a network
  call succeeded, a run started/finished, a fallback was taken deliberately (and the
  data is labeled accordingly). One line per boundary crossing, not per loop iteration.
- **WARNING**: something degraded but the run continues — a provider was skipped
  (missing key), a value fell back to a default, a non-fatal resolution failed (e.g. git
  SHA). Always actionable: state what degraded and, where known, why.
- **ERROR**: the current operation failed and did not produce its result — an ingestion
  batch raised, a backtest run aborted. Reserve for failures the caller couldn't route
  around; a per-venue failure inside `fetch_all` that still returns partial data is a
  WARNING (the batch succeeded), not an ERROR.

## Mandatory logging boundaries

Every crossing of these boundaries logs at least one line (INFO or higher):

- **Disk I/O**: cold-store writes/reads, snapshot writes, results artifacts.
- **Network I/O**: every external call (ENTSO-E, ERCOT/GridStatus, GPU marketplaces) —
  success and failure both.
- **Fallbacks and bascules**: any real→simulated or live→cold-store→synthetic switch
  (rule `forward-real-simulated`). Log the label actually used, not just that a fallback
  exists in the code.
- **Data rejections**: a venue skipped (missing key), a malformed row dropped, a
  point-in-time guard rejecting a future-dated observation.

## Forbidden

- `print()` for anything but the two documented exceptions: the `guard_write.py` hook
  (stdlib-only, runs outside the venv) and the one-line CLI summary of
  `infra/collectors/*_backfill.py` (operational output, not a log record).
- Silent `except Exception: return "unknown"` (or any bare degraded default) with no
  accompanying `logger.warning`. If a failure is worth a fallback value, it is worth one
  line explaining why the fallback fired.
- A library module (`core/`, project `src/`) calling `configure_logging`,
  `logging.basicConfig`, or attaching its own handler. That decision belongs to the one
  entry point that owns the process's console output.
- Raw `logging.getLogger(...)` anywhere outside `core/utils/logging.py` itself — always
  go through `get_logger`.

## Invariants

- **Git SHA**: every record emitted after `configure_logging()` carries the short git SHA
  in `%(git_sha)s` (stamped process-wide via a `LogRecordFactory`, not a per-call-site
  concern). Resolution failure logs a `WARNING` once; it never degrades to a silent
  `"unknown"` with no trace.
- **Real/simulated provenance**: when the call site knows the real/simulated status of
  what it's logging (rule `forward-real-simulated`), pass `get_logger(name,
  simulated=...)` so the line carries `[real]`/`[simulated]`. Omit only when the log site
  has no such notion — never guess a default.
- **Secrets**: any message that might echo request/response internals (HTTP client
  exceptions in particular) goes through `sanitize_for_log` before reaching a log call.

## Why `configure_logging` instead of `basicConfig`

`logging.basicConfig()` at module import time (the pre-V7.1 pattern in several runners)
configures logging as a side effect of `import`, which silently wins or loses depending on
import order the moment two such modules are imported together in the same process
(pytest collecting multiple runners, a notebook importing two of them). `configure_logging`
is idempotent and is only ever invoked from the one place in a process that should own
console output — the entry point, not the library.
