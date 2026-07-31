# Compute Quant Lab — entry points.
#
# Targets are written for POSIX sh and work under Git Bash on Windows, which
# is the primary development environment here. Every recipe goes through `uv`
# so the toolchain never depends on an activated virtualenv.

SHELL := /bin/sh

# Test suites are run one directory at a time: each projects/*/tests uses a
# bare `from conftest import ...`, so a single pytest process would hit
# module-name collisions between projects (see pyproject.toml).
TEST_DIRS := tests \
             core/backtest/tests \
             core/features/tests \
             core/ingestion/energy/tests \
             core/ingestion/providers/tests \
             core/models/tests \
             core/signals/tests \
             core/storage/tests \
             infra/collectors/tests \
             infra/mcp-servers/*/tests \
             projects/*/tests

CRATES := core/pricing/_kernel \
          core/backtest/_loop \
          projects/04_compute_index_curve/forward_engine

.DEFAULT_GOAL := help
.PHONY: help install kernels test lint fmt demo clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Sync the environment and build the Rust kernels
	uv sync --extra dev
	@$(MAKE) kernels

kernels: ## Build the three Rust extension modules
	@for c in $(CRATES); do \
		echo "== maturin develop $$c =="; \
		uv run maturin develop -m "$$c/Cargo.toml" || exit 1; \
	done

test: ## Run every test suite in isolation
	@ran=0; \
	for d in $(TEST_DIRS); do \
		[ -d "$$d" ] || continue; \
		echo "== pytest $$d =="; \
		uv run pytest -q "$$d" || exit 1; \
		ran=$$((ran + 1)); \
	done; \
	echo "== $$ran suites =="; \
	[ "$$ran" -ge 18 ] || { echo "Too few suites ($$ran < 18)" >&2; exit 1; }

lint: ## Run ruff and mypy
	uv run ruff check .
	uv run mypy core

fmt: ## Auto-format and auto-fix
	uv run ruff format .
	uv run ruff check --fix .

demo: ## Launch the GPU spot benchmark dashboard
	uv run streamlit run projects/13_compute_benchmark/dashboard/app.py

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
