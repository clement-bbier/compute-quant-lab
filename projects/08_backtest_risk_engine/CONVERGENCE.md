# P08 → Convergence

Patchs touchant la **zone protégée** (`pyproject.toml`, `.claude/`, `core/utils/`) ou
d'autres modules : préparés ici, **non appliqués** dans le worktree P08. À appliquer
par la session de convergence (pilote `integration`).

---

## 1. `pyproject.toml` (racine)

### 1a. Tests P08 découverts par pytest
`core/backtest/tests/` n'est pas sous `tests/` (P08 n'écrit que dans son module).
```toml
[tool.pytest.ini_options]
testpaths = ["tests", "core/backtest/tests"]
```

### 1b. Build du noyau Rust (boucle OBLIGATOIRE)
Le subcrate `core/backtest/_loop/` est autonome (maturin). Le moteur importe en dur
le module compilé `backtest_loop` ; il doit donc être installé dans l'environnement.
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.10", "pre-commit>=3.7", "maturin>=1.7"]
```
Étape d'install (dev + CI), après `uv sync --extra dev` :
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
```
> CI : ajouter une étape « install Rust toolchain (stable) + maturin develop » **avant**
> `pytest`/`mypy`, sinon l'import du moteur échoue. `core/backtest/_loop/target/` est
> gitignoré (artefacts), `Cargo.lock` est versionné (build reproductible).

### 1c. (optionnel) exclusions outillage
```toml
[tool.ruff]
extend-exclude = ["core/backtest/_loop/target"]
```

---

## 2. Rule candidate `.claude/rules/backtest-mlflow-logging.md`
Path-scopée `core/backtest/**` + `projects/**`. À créer via `agent-architect` / `/new-agent`.

> # Reproductibilité des backtests
> - Tout backtest DOIT logger un run MLflow contenant : params, métriques, **SHA git**
>   et **version DVC** des données. Utiliser `core.backtest.tracking.tracked_run`.
> - Aucune métrique de stratégie publiée sans run MLflow rejouable (`run_id`).
> - Tracer le nombre d'essais (`n_trials`) pour le multiple testing (deflated Sharpe au
>   palier institutionnel). S'articule avec `backtest-runner` (exécution) et
>   `risk-validator` (adversaire).

---

## 3. `core/utils/tracking.py` (module voisin, non possédé)
Remonter la logique de version DVC (aujourd'hui dans `core/backtest/tracking.py`) en
amont, pour que **tout** le labo en hérite, et choisir un backend MLflow non-déprécié.
- Ajouter le tag `dvc_version` dans `core.utils.tracking.run` (cf. `dvc_version()` P08).
- **MLflow 3.14** met le file-store en *maintenance mode* : il lève sans
  `MLFLOW_ALLOW_FILE_STORE=true` (workaround actuel de `run_demo.py`). Décider à l'échelle
  du labo : opt-out file-store **ou** backend `sqlite:///…`. Aligner avec la convention
  « experiments/ » du CLAUDE.md racine (relocaliser le tracking URI hors `projects/08`).

---

## 4. `references/` (possédé par `feature/research`) — via `literature-scout`
Distiller pour le palier institutionnel 3b :
- Bailey & López de Prado — *Deflated Sharpe Ratio*, *The Probability of Backtest Overfitting*.
- López de Prado — purged k-fold + embargo (anti-fuite train/test temporel).

---

## 5. Divergence à harmoniser : intégration Rust P01 ↔ P08
- **P01** : noyau Rust en **fallback** (`skipif(_kernel is None)`, oracle Python par défaut).
- **P08** : noyau Rust **obligatoire** (import dur, pas de fallback runtime).
Choisir une convention labo unique (probablement : obligatoire en CI, fallback en dev rapide).

---

## 6. Gap hérité (signalé par P01) : `core.utils`
`core.utils.logging` et `core.utils.config` sont absents. P08 a contourné par DI (pas de
`print`, pas de chemin en dur). À créer côté `core/utils/` pour standardiser logging/config.
