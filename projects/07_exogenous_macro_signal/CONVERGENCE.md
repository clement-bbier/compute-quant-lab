# P07 → Convergence

Patchs touchant la **zone protégée** (`pyproject.toml`, `.claude/`, `.gitignore`,
`CLAUDE.md` racine) ou des modules non possédés : préparés ici, **non appliqués**
dans le worktree P07. À appliquer par la session de convergence (pilote `integration`).
P07 n'a écrit que dans `core/features/` + `projects/07_exogenous_macro_signal/`.

---

## 1. `pyproject.toml` (racine) — tests P07 découverts par pytest
Les tests P07 vivent dans les modules possédés (pas sous `tests/`). La gate globale
`pytest -q` ne les collecte pas tant que `testpaths` ne les inclut pas (même cas que P08 §1a).
```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "core/features/tests",                       # ← P07
    "projects/07_exogenous_macro_signal/tests",  # ← P07
]
```
> En attendant, P07 lance explicitement
> `pytest core/features/tests projects/07_exogenous_macro_signal/tests`.

## 2. `.gitignore` (racine) — pointeurs DVC du brut exogène (même blocage que P01 §3)
`dvc add data/raw/exogenous/*.parquet` **réussit** (cache peuplé, `.dvc` créés) mais le
motif `data/raw/*` **gitignore aussi les pointeurs `.dvc`** → impossible de committer la
référence de données. La DoD « brut versionné DVC » est donc atteinte *localement* mais
le pointeur n'est pas committable depuis le worktree.
- **Fix** : exception pour les pointeurs, p. ex.
  ```gitignore
  !/data/raw/**/*.dvc
  !/data/raw/**/.gitignore
  ```
- À fusionner avec le fix jumeau demandé par P01 (`data/interim`, `data/processed`).

## 3. Baseline tests : noyaux Rust à compiler (hérité P08 §1b)
La suite globale ne se collecte pas dans un worktree neuf tant que `backtest_loop` (P08)
et `_kernel` (P01) ne sont pas compilés. P07 a dû lancer, avant `pytest -q` :
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run maturin develop -m core/pricing/_kernel/Cargo.toml
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml
```
> Confirme le besoin (déjà signalé P08) d'une étape « maturin develop » en CI **avant**
> `pytest`/`mypy`. P07 n'ajoute aucun crate Rust (features 100 % Python).

## 4. Registre des sources (`CLAUDE.md` racine §3) — gaz / météo
Faire passer « Marchés gaz/météo » de *backlog* à *en cours (P07, synthétique)* et acter
le besoin d'un **connecteur réel** (prix gaz day-ahead, HDD/CDD météo) — ressort de
`data-engineer`. Tokens → `.env` + `.worktreeinclude` (var `EXOGENOUS_API_TOKEN`, lue par
`projects/07/src/sources.py`, aujourd'hui repli synthétique déterministe loggué).

## 5. `core/utils/` — promouvoir la normalisation UTC (owner : core/utils)
`core.features.builders._to_utc_index` **duplique** `core.pricing._timeindex.to_utc_index`
(règle d'intégrité « UTC tz-aware, pas de naïf »). À remonter dans `core.utils` (p. ex.
`core.utils.timeindex.to_utc_index`) pour que pricing, features et futurs modules partagent
une frontière unique testée.

## 6. Contribution utilisateur — `DEFAULT_PUBLICATION_LAGS`
La table des lags de publication par défaut (`core/features/builders.py`) est **fixée par le
directeur de recherche** (valeurs conservatrices + justification par variable). Au câblage du
connecteur réel (item §4), recalibrer chaque lag sur le **vrai** calendrier de publication
(jour-ouvré, fuseau, délai de révision) et, si la source expose des millésimes, alimenter
directement les frames vintage (chemin révisions déjà géré par `as_of_snapshot`).

## 7. Nouveaux employés / références (croissance labo, prompt §8)
- `risk-validator` : attaquer chaque feature (look-ahead résiduel, corrélation spurieuse,
  data snooping sur le faible historique compute réel).
- `literature-scout` : drivers énergie (gaz, météo, HDD/CDD) et datacenter buildout → `references/`.

## 8. État de la DoD (prompt §11)
- [x] Tests verts : anti look-ahead (lag, garde-fou rouge), alignement/fuseau, révisions, builders — 16 + 4.
- [x] `ruff check .` & `mypy core` verts.
- [x] Run MLflow loggué (params + lags + SHA + DVC) ; brut DVC **tracké localement** (pointeur bloqué, §2).
- [x] Synthèse `results/SYNTHESIS.md` + `run_summary.json` (lead, pouvoir prédictif, pièges).
- [x] Rien écrit hors `core/features/` + `projects/07_…` (hors artefacts data/MLflow git-ignorés). Commit branche, ni merge ni push.
