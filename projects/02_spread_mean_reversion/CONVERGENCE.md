# P02 → Convergence

Patchs touchant la **zone protégée** (`pyproject.toml`, `.claude/`, `core/`) ou d'autres modules :
préparés ici, **non appliqués** dans le worktree P02. À appliquer par la session de convergence
(pilote `integration`).

---

## 1. `pyproject.toml` (racine)

### 1a. Tests P02 découverts par pytest
`projects/02_spread_mean_reversion/tests/` n'est pas dans `testpaths` (P02 n'écrit que dans son
module). Aligner sur la convention déjà ouverte par P04.
```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/02_spread_mean_reversion/tests",
]
```
> En attendant : lancer explicitement `uv run pytest projects/02_spread_mean_reversion -q`.

---

## 2. Connecteur ENTSO-E dans `core/ingestion/` (jambe énergie générique)
La jambe énergie réelle est aujourd'hui chargée depuis `projects/02_.../src/data_sources.py`
(`load_energy_entsoe`, appel direct à `entsoe-py`). C'est une brique **réutilisable** (P03, P06… en
auront besoin) : elle appartient à `core/ingestion/`. Proposition :
- `core/ingestion/energy_market.py` : `EntsoeSource` (token `ENTSOE_API_TOKEN`), parsing → série
  €/MWh UTC tz-aware, gap-filling documenté (rule `data-integrity`).
- Versionner la série réelle via DVC (`data/raw/energy/…`) avant tout backtest publié.

---

## 3. Câblage Silicon Data (`core/ingestion/compute_index.py`)
`SiliconDataSource.fetch` lève `NotImplementedError`. Pour un backtest sur **historique compute réel
profond**, brancher l'API SDH100RT (token `SILICONDATA_API_TOKEN` + endpoint). À décider avec P04
(propriétaire de `core/ingestion` jambe compute).

---

## 4. `references/` (possédé par `feature/research`) — via `literature-scout`
Distiller pour le palier institutionnel 3b :
- Ornstein-Uhlenbeck / demi-vie de mean-reversion (Avellaneda & Lee ; Ernie Chan).
- Engle-Granger (1987), Johansen — valeurs critiques et stabilité hors échantillon.
- **Deflated Sharpe Ratio** (Bailey & López de Prado) : indispensable dès qu'on scanne des seuils z
  (`n_trials` est tracé dans MLflow mais aucun ajustement n'est encore appliqué).

---

## 5. Employé manquant : agent `risk-validator` (croissance labo, prompt §8)
Le `CLAUDE.md` racine §6 décrit `risk-validator` (adversaire) mais il **n'est pas enregistré** dans
l'environnement (vérifié : absent de la liste des agents). L'audit `/backtest-pitfalls` de P02 a donc
été fait manuellement. À créer via `agent-architect` / `/new-agent` (écrit dans `.claude/agents/`,
zone protégée → convergence). Spec proposée : adversaire en lecture seule, traque look-ahead /
overfitting / data-snooping / coûts irréalistes, refuse de croire tout Sharpe > 2 sans deflated
Sharpe + walk-forward. Idem `infra-engineer` (également absent).

## 6. Rule candidate `.claude/rules/` (optionnel)
Une rule path-scopée `projects/**/strategy*.py` rappelant : « toute stratégie implémente le
`Strategy` Protocol de P08 et n'accède qu'à `view.history()`/`view.latest()` (≤ t) ». S'articule
avec la rule `quant-no-lookahead` existante.
