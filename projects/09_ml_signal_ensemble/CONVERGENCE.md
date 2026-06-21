# P09 → Convergence

Patchs touchant la **zone protégée** (`pyproject.toml`, `.claude/`, `core/` hors `core/models/`)
ou d'autres modules : préparés ici, **non appliqués** dans le worktree P09. À appliquer par la
session de convergence (pilote `integration`).

---

## 1. `pyproject.toml` (racine) — découverte des tests par pytest

`core/models/` (possédé par P09) et ses tests ne sont pas dans `testpaths`, et le projet P09 non
plus. Aligner sur la convention déjà ouverte par P04/P02.

```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "core/models/tests",                       # ← P09 (couche modèle)
    "projects/04_compute_index_curve/tests",
    "projects/02_spread_mean_reversion/tests",
    "projects/09_ml_signal_ensemble/tests",    # ← P09 (projet)
]
```

> En attendant : `uv run pytest core/models/tests projects/09_ml_signal_ensemble -q`.
> ⚠️ La CI lance chaque dossier **en isolation** (collision de `conftest` entre projets).
> Les tests de `core/models/tests` **importent `core.backtest`** → ils exigent le noyau Rust
> compilé (`maturin develop -m core/backtest/_loop/Cargo.toml`), comme déjà documenté pour P05/P08.

---

## 2. Promotion de briques dans `core/features/` (croissance labo, prompt §8)

- Les transforms causales dérivées du spread (`SpreadFeatureSpec` / `FeaturePipeline._spread_features`
  dans `core/models/pipeline.py`) recoupent les transforms exogènes de `core/features` (`lag_feature`,
  `rolling_mean_feature`, `diff_feature`). À **unifier** dans `core.features` pour une seule source de
  vérité du feature engineering point-in-time (P03/P07/P09).
- `InMemoryExogenousSource` (dans `projects/09_.../src/synthetic.py`) est une implémentation de
  référence du protocole `ExogenousSource` : candidate à `core/features` (utile à tout projet ML/test).

---

## 3. Employé manquant : agent `risk-validator` (croissance labo, prompt §8 — OBLIGATOIRE)

Le `CLAUDE.md` racine §6 décrit `risk-validator` (adversaire) et le prompt P09 le rend **obligatoire**
avant de croire un Sharpe, mais il **n'est toujours pas enregistré** dans l'environnement (déjà signalé
par P02). L'audit `/backtest-pitfalls` de P09 a donc été conduit **à la main**
([results/SYNTHESIS.md](results/SYNTHESIS.md)). À créer via `agent-architect` / `/new-agent` (écrit
dans `.claude/agents/`, zone protégée → convergence). Spec proposée : adversaire **lecture seule**,
traque look-ahead / overfitting / data-snooping / coûts irréalistes ; refuse tout Sharpe « trop beau »
sans **deflated Sharpe** (avec vrai `n_trials`) + **walk-forward** ; exige la reproductibilité MLflow.

---

## 4. `references/` (possédé par `feature/research`) — via `literature-scout`

Distiller pour le palier institutionnel (3b), socle théorique de P09 :
- **López de Prado**, *Advances in Financial Machine Learning* : purged k-fold + embargo,
  **Deflated Sharpe Ratio**, backtest overfitting (PBO), feature importance robuste (MDA/MDI).
- **Bailey & López de Prado (2014)**, *The Deflated Sharpe Ratio*.
- Séquentiel : LSTM / **Temporal Fusion Transformer** (Lim et al.) pour le palier supérieur.

---

## 5. Note d'intégration (pas un patch, un rappel)

`core/models/` dépend en lecture de `core.pricing` (P01), `core.features` (P07), `core.backtest` (P08)
— tous supposés présents dans `integration`. `core.models.strategy` importe volontairement
`core.backtest.protocols` (et non le package `core.backtest`) là où c'est possible, mais l'`__init__`
de `core.backtest` reste tiré dès qu'on touche le moteur → **noyau Rust requis** au runtime du backtest.
