# Compute Quant Lab

Quant research lab treating **compute** (GPU rental) as an asset class,
arbitraged against its raw material: **electricity** (*digital spark spread*).

## Getting started
```bash
uv sync --extra dev
uv run pytest          # verifies the pricing module
pre-commit install
```

## Structure
See `CLAUDE.md` (full lab index, organization, sources, agents).

## Agentic orchestration
The `.claude/` folder configures the lab for agentic work: rules (quality),
skills (procedures), agents (the "staff"), hooks (deterministic guardrails).
