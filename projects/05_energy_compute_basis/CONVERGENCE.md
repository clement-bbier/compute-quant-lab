# Patches de convergence — P05

> La zone protégée (`pyproject.toml`, `CLAUDE.md` racine, `.claude/`, `.mcp.json`) ne se
> modifie **que** via la session de convergence (cf. `docs/git-workflow.md` §3). P05 prépare
> ici les patches à remonter ; il ne les applique pas lui-même.

## 1. `pyproject.toml` — découverte des tests P05 (REQUIS)

Les tests de P05 vivent dans `projects/05_energy_compute_basis/tests/` mais ne sont pas
collectés par un `pytest` sans argument tant qu'ils ne figurent pas dans `testpaths`
(même schéma que P04). Patch à appliquer à la convergence :

```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/05_energy_compute_basis/tests",   # ← ajout P05
]
```

En attendant le merge, lancer explicitement : `pytest projects/05_energy_compute_basis -q`.

## 2. Build des noyaux Rust dans le worktree (ENVIRONNEMENT, pas un patch source)

La baseline complète exige les extensions Rust compilées (sinon `core/backtest` lève
`ModuleNotFoundError: backtest_loop`). Préparer chaque worktree avec :

```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run maturin develop -m core/pricing/_kernel/Cargo.toml
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml
```

Aucune source `core/` n'est modifiée (cibles `target/` gitignorées, install dans le venv).
