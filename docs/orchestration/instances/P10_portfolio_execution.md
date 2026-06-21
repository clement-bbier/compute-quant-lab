<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P10 — portfolio_execution

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`,
> les skills `/run-backtest`, `/backtest-pitfalls`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : P10 — couche Desk (agrégation). **Branche** : `feature/P10-portfolio_execution`.
- **Worktree** : `git worktree add ../lab-P10 -b feature/P10-portfolio_execution integration`
- **Module possédé (écris UNIQUEMENT ici)** : `projects/10_portfolio_execution/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, tout `core/` (lecture seule).

## 1. Thèse
Transformer des **signaux** (mean-reversion P02, dérivés P06, ML P09) en un **portefeuille**
qualité desk : pondération sous budget de risque, **modèle d'exécution et de coûts** réaliste,
PnL net. C'est la couche qui répond à « combien on met, et qu'est-ce qu'il reste après frais ».

## 2. Découplage (clé du parallélisme)
P10 **ne dépend pas des entrailles** de P02/P06/P09 : il consomme des **signaux génériques** via
l'abstraction `Strategy`/signal de **P08** (`core.backtest`, déjà dans `main`). Tu construis et testes
contre des **producteurs de signaux mockés** (in-memory) ; les vrais (P02, P06, P09) se branchent à la
**convergence** sans changer ton code. Tu peux donc tourner **en parallèle** de P09.

## 3. Deux paliers
- **PoC-now** : (a) construction de portefeuille (pondération inverse-vol / budget de risque, ≥ 2
  signaux mockés) ; (b) **modèle d'exécution/coûts** (frais, slippage, impact simple) ; (c) backtest
  agrégé via P08 → PnL **net**, Sharpe, drawdown, turnover, contribution par signal.
- **Institutional-target** : optimiseur (Markowitz/risk-parity contraint), exécution live, limites desk, capacité.

## 4. Architecture (SOLID / DI)
`PortfolioConstructor` (combine des signaux → poids), `ExecutionModel` (poids → trades nets de coûts),
injectés dans le backtest P08 comme une `Strategy` composite. Producteurs de signaux derrière une
abstraction (mock au PoC, P02/P06/P09 ensuite : OCP). Fonctions pures, coûts explicites (rules).

## 5. Code à faire grossir
- **Dans `projects/10_portfolio_execution/`** : `src/portfolio.py`, `src/execution.py`,
  `src/run_desk.py` (MLflow), `notebooks/`, `results/`.
- **Dans `core/`** : RIEN (lecture seule). Ce qui devient générique (optimiseur) → convergence.

## 6. Tests-first
(a) pondération sur signaux connus → poids attendus (somme, budget de risque) ; (b) **coûts
d'exécution** : turnover × frais correct ; (c) **anti look-ahead** (poids à t sur signaux ≤ t) ;
(d) PnL net = PnL brut − coûts ; (e) DI : tourne avec des signaux mockés. pytest, déterministe.

## 7. Reproductibilité
MLflow via `core.backtest.tracking` (poids, coûts, signaux utilisés + SHA + DVC). Seed fixe.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** : `backtest-runner` (exécution), **`risk-validator`** (le PnL agrégé cache-t-il un overfit composite ?).
- **Références** : construction de portefeuille robuste, risk parity, modèles d'impact/coût → `literature-scout`.
- **Convergence** : `pyproject.toml` testpaths `projects/10_…/tests` ; brancher les vrais signaux P02/P06/P09.

## 9. Dépendances
- **Amont (runtime, via convergence)** : P02, P06, **P09**, **P08**. **Au build** : seulement l'abstraction signal de **P08** (mock le reste).
- **Modules core requis** : `core.backtest` (lecture). **Externe** : numpy/pandas (présents).

## 10. Risques & angles morts
**Agréger des signaux overfittés** = sur-confiance composite ; corrélations ignorées ; coûts
d'exécution sous-estimés (le tueur de PnL réel) ; look-ahead dans la pondération ; capacité non modélisée.
Le `risk-validator` doit attaquer le PnL **net**, pas brut.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (pondération, coûts, anti look-ahead, PnL net, DI mockée).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Backtest desk loggué MLflow (PnL net + métriques + SHA + DVC) sur signaux mockés.
- [ ] Synthèse `results/` : PnL net, contribution par signal, sensibilité aux coûts, limites.
- [ ] Rien écrit hors `projects/10_…`. Commit sur la branche. Ni merge ni push.
