---
paths:
  - "**/*.py"
---
# Python code quality

- Type hints mandatory on every public function. `mypy core` must pass.
- No magic numbers: constants (PUE, GPU power draw, etc.) live in a config
  module or are named arguments, never hardcoded in the logic.
- Short NumPy-style docstrings on `core/` functions.
- No `print` for logging: use `core.utils.logging`.
- Pure functions on the `core/` side (no hidden I/O side effects); I/O is explicit.
