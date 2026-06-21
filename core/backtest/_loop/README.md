# `backtest_loop` — noyau Rust (phase 2)

Subcrate **maturin autonome** : boucle d'accumulation du PnL point-in-time, chemin
runtime de la phase 2 du moteur. Réplique bit-à-bit l'oracle Python
`core/backtest/reference_loop.py` (parité testée par `test_parity`).

## Build (prérequis — la boucle Rust est OBLIGATOIRE, pas de fallback runtime)

```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
```

Installe le module compilé `backtest_loop` dans le venv. `core.backtest.engine`
l'importe en dur : sans ce build, l'import du moteur échoue (choix assumé).

> ⚠️ Zone protégée : le câblage de ce build dans le `pyproject.toml` racine + la CI
> Rust est un **patch de convergence** (voir `projects/08_backtest_risk_engine/CONVERGENCE.md`).
