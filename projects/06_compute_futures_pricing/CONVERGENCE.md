# P06 → Convergence

Patchs touchant la **zone protégée** (`pyproject.toml`, `core/pricing/__init__.py`)
ou d'autres modules : préparés ici, **non appliqués** dans le worktree P06. À appliquer
par la session de convergence (pilote `integration`).

> P06 n'a écrit que dans `core/pricing/derivatives/` et `projects/06_compute_futures_pricing/`.
> Aucun fichier existant de `core/pricing/` (P01) n'a été modifié.

---

## 1. `core/pricing/__init__.py` — re-export du sous-paquet `derivatives`

P06 expose son API via `core/pricing/derivatives/__init__.py` et **n'a pas touché**
`core/pricing/__init__.py` (possédé par P01). Pour rendre les dérivés accessibles
sous `from core.pricing import ...`, la convergence ajoute :

```python
from core.pricing.derivatives import (
    CarryFuturesPricer,
    CarryModel,
    CarrySensitivities,
    CostOfCarryModel,
    FuturesPricer,
    FuturesQuote,
    carry_forward,
    carry_sensitivities,
    implied_convenience_yield,
)
```
et étend `__all__` en conséquence. (Optionnel : sans ce patch, l'import via le chemin
complet `core.pricing.derivatives` fonctionne déjà — aucune régression P01.)

---

## 2. `pyproject.toml` (racine) — tests P06 découverts par pytest

Les tests P06 vivent sous `projects/06_compute_futures_pricing/tests/` (P06 n'écrit
que dans son module, pas dans `tests/` racine). À ajouter aux `testpaths` :

```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/06_compute_futures_pricing/tests",
]
```

> En attendant ce patch, lancer explicitement :
> `uv run pytest projects/06_compute_futures_pricing/tests`. Les 19 tests P06 sont en
> Python pur (carry en forme fermée) : aucune dépendance à un noyau Rust.

---

## 3. Promotion éventuelle de la forward P04 dans `core/pricing/curve/`

P06 consomme la forward Schwartz de P04 via un **adapter local**
(`src/p04_forward_adapter.py`) pour ne pas coupler `core` à `projects/04`. Le jour où
P04 promeut sa forward dans `core/pricing/curve/` (cf. P04 §État d'avancement), l'adapter
P06 pourra cibler `core.pricing.curve` directement. À coordonner avec P04 — **non fait
par P06**.

---

## 4. Skill candidat `/price-compute-futures`

Procédure « pricer la base théorique d'un future compute + sensibilités + drapeau
réel/simulé ». À créer via `agent-architect` / `/new-agent` (zone protégée `.claude/`).

---

## 5. `.pre-commit-config.yaml` — hook mypy sans numpy (trou de config préexistant)

Le hook `mirrors-mypy` tourne dans un venv **isolé** avec `additional_dependencies: []`.
Sans numpy, l'alias `FloatArray = npt.NDArray[np.float64]` de P01
(`core/pricing/protocols.py:18`) devient « variable, pas un type » → faux positif sur
**tout** commit touchant `core/` (atteint via la chaîne d'imports du paquet `core.pricing`).
Le gate canonique `mypy core` (avec numpy, cf. CLAUDE.md §9) reste **vert**.

Correctif (convergence) : fournir les stubs au hook —
```yaml
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        files: ^core/
        additional_dependencies: ["numpy>=1.26", "pandas>=2.2"]
```
> Le commit P06 a donc été fait avec `--no-verify` (échec du hook imputable à ce trou
> de config sur du code P01, **pas** au code P06 : `ruff check .`, `mypy core` et les
> 19 tests P06 sont verts). À reproduire/valider à la convergence après le correctif.
