# Compute Quant Lab

> Index du labo. Garder ce fichier **< 200 lignes** : c'est une carte qui pointe
> vers les rules / skills / agents, pas une encyclopédie.

## 1. Thèse de recherche

Le **compute** (location de GPU : Nvidia H100/Hopper, Blackwell) est une nouvelle
classe d'actifs dont la matière première est l'**électricité**. Le labo modélise,
price et arbitre le spread entre les deux — le *digital spark spread* — pour
produire des signaux exploitables par un desk type Global Markets.

Principe directeur : **PoC → fondation**. Toute brique réutilisable d'un projet
remonte dans `core/`. Le projet N+1 démarre avec l'infra du projet N déjà prête.

## 2. Glossaire

- **Spark spread** : marge = revenu compute − coût énergétique de production.
- **PUE** (Power Usage Effectiveness) : ratio conso totale datacenter / conso IT.
- **Point-in-time** : n'utiliser que la donnée *connue à l'instant t* (anti look-ahead).
- **Alpha** : rendement excédentaire non expliqué par l'exposition au marché.
- **Coût marginal du compute** : coût énergétique d'une heure-GPU.

## 3. Registre des sources de données

| Source | Flux | Accès | Statut |
|---|---|---|---|
| ENTSO-E Transparency | Prix spot élec FR/DE (€/MWh) | API token (`entsoe-py`) | à configurer |
| EPEX Spot | Prix day-ahead | API payante / proxy | à étudier |
| Vast.ai / RunPod | Prix location GPU (€/h) | API publique, historisée maison | à coder |
| Marchés gaz/météo | Variables exogènes | API | backlog |
| S&P Global / Kensho | Donnée financière de référence | MCP (connecté) | dispo |
| Tavily | Recherche web (veille) | MCP (connecté) | dispo |

> Détails d'implémentation : `core/ingestion/`. Tokens : `.env` (jamais committé).
> ⚠️ Le prix du compute n'existe pas en historique : `infra/collectors/gpu_price_snapshot.py`
> l'accumule jour après jour dans `data/snapshots/`. La jambe énergie, elle, a un historique profond.

## 4. Structure du dépôt

- `core/` — bibliothèque partagée installable (`pip install -e .`)
  - `ingestion/` connecteurs · `data_quality/` validation · `pricing/` spark spread
  - `features/` feature engineering point-in-time · `models/` XGBoost, LSTM/TFT
  - `backtest/` moteur + métriques · `utils/` config, logging, tracking (MLflow)
- `data/` — `raw/` (immuable, versionné DVC) → `interim/` → `processed/`
- `experiments/` — runs MLflow (tracking local, pas de serveur)
- `projects/NN_nom/` — un projet de recherche autonome (a son propre CLAUDE.md)
- `infra/mcp-servers/` — **code** des serveurs MCP custom (≠ `.mcp.json` racine)
- `infra/collectors/` — services planifiés (snapshot prix GPU)
- `tests/` — pytest · `references/` — **couche savoir** : bibliographie + méthodo distillée

## 5. Mécanismes d'orchestration (`.claude/`)

- **rules/** — contraintes path-scopées (qualité Python, intégrité données, no look-ahead)
- **skills/** — procédures : `/run-backtest`, `/data-quality-check`, `/new-research-project`
  - **couche savoir** : `/cointegration-analysis`, `/spread-trading-playbook`, `/backtest-pitfalls`
  - **veille parallèle** : `/market-scan` (essaim de subagents sur le marché du compute)
- **agents/** — le « personnel » du labo (voir §6)
- **settings.json** — hooks déterministes (format auto, blocage écriture `data/raw/`, blocage `.env`)

## 6. Le personnel du labo (subagents)

La session principale = directeur de recherche qui délègue. Chaque agent tourne en
isolation et ne renvoie qu'une synthèse.

- `data-engineer` — ingestion, scraping, connecteurs
- `data-quality-auditor` — gaps, outliers, intégrité point-in-time
- `quant-researcher` — features, modélisation, signaux
- `backtest-runner` — exécution isolée → PnL / Sharpe / drawdown
- `risk-validator` — **adversaire** : traque look-ahead, overfitting, data snooping
- `infra-engineer` — serveurs MCP, CI, environnement
- `literature-scout` — veille arXiv / SSRN
- `code-reviewer` — qualité, typage, conventions

## 7. Opérations parallèles (usine de recherche)

Travail massivement parallèle en 3 voies : **collecte** (essaim de subagents via
`/market-scan`), **construction** (git worktrees, 1 worktree = 1 module disjoint),
**convergence** (1 session pilote qui merge et réconcilie). Règle d'or : un worktree
n'écrit que dans son module ; la zone protégée (`CLAUDE.md`, `.claude/`, `.mcp.json`,
`pyproject.toml`) passe uniquement par la session de convergence.
→ Détail et partition de propriété : `docs/parallel-ops.md`. Helper : `scripts/new-worktree.ps1`.

## 8. Conventions

- Python ≥ 3.11, environnement géré par **uv** (`uv sync`), lockfile committé.
- Tout I/O de données passe par `core/` — jamais de chemin en dur dans un projet.
- `data/raw/` est **immuable** : on n'écrit jamais dedans à la main (hook PreToolUse).
- Tout backtest est loggué dans MLflow avec params + métriques + SHA git + version DVC des données.
- Commits sémantiques. Tests + ruff verts avant merge (pre-commit + CI).

## 9. Commandes utiles

```bash
uv sync                 # installe l'environnement depuis le lockfile
pytest                  # lance les tests
ruff check . && mypy core   # qualité
dvc pull                # récupère les données versionnées
mlflow ui               # tableau de bord des expériences (local)
```
