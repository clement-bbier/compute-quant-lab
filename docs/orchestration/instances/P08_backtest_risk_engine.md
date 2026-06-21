<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P08 — backtest_risk_engine

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Ne code
> rien tant que le plan n'est pas validé. Lis d'abord le `CLAUDE.md` racine, ce
> fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`, les skills `/run-backtest`
> et `/backtest-pitfalls`, et le module que tu possèdes. Ton livrable = un **plan**.

## 0. Identité & cadre Git
- **ID projet** : P08 — racine de la couche Fondation (aucune dépendance amont).
- **Branche** : `feature/P08-backtest_risk_engine`
- **Worktree** : `git worktree add ../lab-P08 -b feature/P08-backtest_risk_engine integration`
- **Module possédé (écris UNIQUEMENT ici)** : `core/backtest/` + `projects/08_backtest_risk_engine/`
- **Zone protégée (NE PAS toucher ici)** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` → tout patch remonte à la convergence.

## 1. Thèse
Aucun résultat n'est crédible sans un moteur de backtest **reproductible** et des
**garde-fous anti look-ahead** intégrés. P08 est la fondation de confiance : chaque
projet de stratégie (P02, P09, P10…) s'y branche. Il opérationnalise la convention
du labo « tout backtest loggué MLflow + SHA git + version DVC ».

## 2. Flux de données vérifiés
P08 est **agnostique aux sources** : il consomme des séries déjà priceées (de P01)
et des signaux de stratégie, mais se définit d'abord contre des **fixtures
synthétiques** (séries connues) pour prouver le moteur sans dépendre d'une donnée externe.

| Entrée | Origine | Forme |
|---|---|---|
| Série de prix / spread | P01 (plus tard) / fixtures | point-in-time, UTC |
| Signal de stratégie | injecté (`Strategy`) | position(t) à partir de données ≤ t |
| Modèle de coûts | injecté (`CostModel`) | frais, slippage |

## 3. Deux paliers
### 3a. PoC-now (preuve exécutable, qualité desk)
Moteur de backtest point-in-time (vectorisé ou événementiel) dans `core/backtest/` :
applique une `Strategy` injectée, calcule PnL, **Sharpe**, **max drawdown**,
turnover, avec **garde-fou look-ahead** qui *échoue* si un signal à t consomme une
donnée > t. Logging MLflow + capture SHA git + version DVC **intégrés au moteur**.
**Polyglotte dès le PoC** : boucle interne du backtest (parcours d'historiques longs)
en **Rust/C++** pour la perf, avec moteur Python de référence pour les tests.
### 3b. Institutional-target (cible desk réel)
Backtest événementiel multi-actifs, modélisation fine d'exécution/impact, walk-forward
et purged CV, Sharpe dégonflé (multiple testing), parallélisation des scénarios.

## 4. Architecture (SOLID / DI)
- `Strategy` (Protocol) : `signal(view_at_t) -> position` (ne voit que ≤ t).
- `CostModel` (Protocol) : `cost(trade) -> €`.
- `MetricsCalculator` (Protocol) : PnL, Sharpe, drawdown, turnover.
- `LookAheadGuard` : enveloppe la vue de données et lève si accès au futur.
- `BacktestEngine` orchestre via abstractions ; stratégies/coûts/métriques **injectés**
  → un nouveau type de stratégie ne modifie pas le moteur (OCP). Le noyau Rust est
  une implémentation interchangeable de la boucle, l'oracle reste Python.

## 5. Code à faire grossir
- **Dans `core/`** : `core/backtest/engine.py`, `core/backtest/metrics.py`,
  `core/backtest/protocols.py`, `core/backtest/guards.py`, noyau Rust `core/backtest/_loop/`.
- **Dans `projects/08_backtest_risk_engine/`** : harnais de démo sur fixtures, notebooks, `results/`.
- **Polyglotte** : boucle interne Rust/C++ (justifiée par la longueur des historiques).

## 6. Tests-first
(a) Métriques sur séries connues (Sharpe/drawdown analytiques) ; (b) **le garde-fou
look-ahead échoue** quand on triche (test rouge attendu) ; (c) **déterminisme** :
mêmes entrées → mêmes sorties au bit ; (d) comptabilité turnover/coûts ; (e) parité
Rust ↔ Python. pytest, vert avant merge. S'appuyer sur `/backtest-pitfalls`.

## 7. Reproductibilité
**Cœur du projet** : chaque run logue dans MLflow params + métriques + **SHA git** +
**version DVC** des données. C'est P08 qui rend la convention du labo exécutable pour
tous. Un run est rejouable depuis son ID MLflow seul.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** (via `agent-architect` + `/new-agent`) : candidate **rule**
  « tout backtest doit logger MLflow (params+métriques+SHA+DVC) » ; s'articule avec les
  agents existants `backtest-runner` (exécution) et `risk-validator` (adversaire).
- **Références** (`references/`) : Bailey & López de Prado (deflated Sharpe, backtest
  overfitting), purged/embargoed CV → `literature-scout`.
- **Sources / MCP** : aucune nouvelle (agnostique aux sources).
- **Skills / rules** : enrichir `/run-backtest` et `/backtest-pitfalls` si des étapes manquent (patch convergence).

## 9. Dépendances
- **Amont (projets)** : aucune (racine) ; consommera `core/pricing/` (P01) une fois
  mergé, mais se valide d'abord sur fixtures.
- **Modules core requis** : `core/utils/` (config, logging, tracking MLflow).
- **Externe** : MLflow (local), DVC, toolchain Rust/C++.

## 10. Risques & angles morts
- **Le moteur lui-même source de look-ahead** → garde-fou testé en rouge.
- **Multiple testing / overfitting** : backtests répétés → prévoir Sharpe dégonflé (palier institutionnel) et tracer le nombre d'essais.
- **Coûts irréalistes** : slippage/frais sous-estimés → modèle de coût explicite et injecté.
- **Fuite in-sample/out-of-sample** : séparation stricte, documentée. Le `risk-validator` doit pouvoir casser le moteur.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (métriques, garde-fou look-ahead en rouge, déterminisme, parité Rust/Python).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Démo sur fixtures loggée MLflow (params + métriques + SHA + version DVC).
- [ ] Synthèse écrite (métriques, limites, pièges couverts).
- [ ] Rien écrit hors `core/backtest/` + `projects/08_…`. Prêt à merger vers `integration`.
