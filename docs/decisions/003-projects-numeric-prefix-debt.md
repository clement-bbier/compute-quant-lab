# 3. `projects/NN_name/` numeric-prefix directories stay non-importable

## Status
Accepted (deliberate debt) — 2026-06

## Context
Project directories are named `projects/01_digital_spark_spread/`,
`projects/02_spread_mean_reversion/`, etc. A leading digit makes a directory
name invalid as a Python package (`import projects.02_spread_mean_reversion`
is a syntax error), which forces every runner script to manipulate
`sys.path` directly (six call sites: P02, P04, P07, P08, P13, P14) and
prevents pytest from collecting multiple project test directories in one
session without `conftest` name collisions (see
[002](002-per-project-ci-testpaths-gap.md)). It is also the reason two
roster entries, "P11" (`core/storage/`) and "P12" (`core/signals/`), are
promotion passes into `core/` rather than directories under `projects/`:
a numbered folder was never a viable home for reusable library code.

## Decision
Keep the `NN_name` numeric prefix. It encodes the research roster order
(P01...P14) at a glance in a directory listing, which was judged more
valuable during active parallel research than importability.

## Consequences
- `sys.path.insert` boilerplate persists in every project runner.
- Per-project pytest isolation (one directory per invocation) is required,
  not incidental — see [002](002-per-project-ci-testpaths-gap.md).
- Renaming to an importable scheme (e.g. `projects/spread_mean_reversion/`
  with an `__init__.py`) would touch all twelve project directories, every
  import site, and all documentation in one pass — estimated 1-2 days,
  conflicting with any concurrent work across the repo. Out of scope until
  a dedicated pass is scheduled; document as assumed debt rather than fix
  incidentally.
