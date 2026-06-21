<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P06 — compute_futures_pricing

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`,
> la rule `.claude/rules/forward-real-simulated.md`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : P06 — couche Stratégie (dérivés). **Branche** : `feature/P06-compute_futures_pricing`.
- **Worktree** : `git worktree add ../lab-P06 -b feature/P06-compute_futures_pricing integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`core/pricing/derivatives/`** (NOUVEAU sous-paquet) + `projects/06_compute_futures_pricing/`
- **Zone protégée / NON touché** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, et **les fichiers existants de `core/pricing/`** (possédés par P01, mergés) — **n'édite PAS `core/pricing/__init__.py`** : expose via `core/pricing/derivatives/__init__.py` et signale le re-export à la convergence.

## 1. Thèse
Les **futures compute** sont annoncés par le CME mais **NON listés** (revue réglementaire).
P06 les **price théoriquement** : carry (cost-of-carry vs convenience yield), base spot/forward,
sensibilités, à partir du **spot Silicon Data** (P04) et de la **courbe forward SIMULÉE** (P04).
Edge : être prêt à valoriser la base le jour du listing.

## 2. Flux de données vérifiés
Spot compute (`core.ingestion`, P04, réel) + courbe forward (`projects/04…/forward`, **SIMULÉE**,
Schwartz 1-facteur). ⚠️ **Tout output de P06 est théorique/simulé** : futures non listés. Drapeau
réel/simulé **obligatoire** (rule `forward-real-simulated`).

## 3. Deux paliers
- **PoC-now** : (a) `FuturesPricer` (modèle de carry : `F = S·e^{(r−y)τ}` et/ou via la forward
  Schwartz de P04) ; (b) **base** = F − S et son évolution ; (c) sensibilités (à r, y, τ).
- **Institutional-target** : surface de futures multi-échéances, calendar spreads, options sur futures, calibration sur le listing réel.

## 4. Architecture (SOLID / DI)
Sous-paquet `core/pricing/derivatives/` : `protocols.py` (`FuturesPricer`, `CarryModel`),
`carry.py`, `futures.py` (dataclass `FuturesQuote` avec champ `simulated: bool` **obligatoire**).
DI : la source forward (P04) est injectée. Fonctions pures (rule python-quality). Réutilise les
patterns de `core.pricing` (P01) sans modifier ses fichiers.

## 5. Code à faire grossir
- **Dans `core/pricing/derivatives/`** : `__init__.py`, `protocols.py`, `carry.py`, `futures.py`.
- **Dans `projects/06_compute_futures_pricing/`** : `src/run_pricing.py`, `notebooks/`, `results/`.

## 6. Tests-first
(a) pricing futures sur **params connus** (carry analytique) ; (b) **base = F − S** ; (c) convergence
`F(τ=0) = S` ; (d) **`FuturesQuote.simulated is True`** — échoue si le drapeau manque ; (e) cohérence
avec la forward P04. pytest, fixtures.

## 7. Reproductibilité
MLflow (modèle, r, y, τ, source forward + SHA + DVC) via `core.utils.tracking`. Seed fixe.

## 8. CROISSANCE DU LABO (obligatoire)
- **Skills/rules** : la rule `forward-real-simulated` **s'applique pleinement** ; candidat skill
  `/price-compute-futures` via `agent-architect`.
- **Références** : cost-of-carry, convenience yield, futures sur commodités non stockables → `literature-scout`.
- **Convergence** : promotion éventuelle de la forward P04 dans `core/pricing/curve/` (à coordonner).

## 9. Dépendances
- **Amont** : **P04** (spot + forward, dans `main`). S'appuie sur les patterns **P01**.
- **Modules core requis** : `core.ingestion`, `core.pricing` (lecture).
- **Externe** : aucune nouvelle (numpy/pandas).

## 10. Risques & angles morts
Futures **non listés** → 100 % théorique, ne JAMAIS présenter comme réel ; **convenience yield**
non observable (hypothèse) ; confusion réel/simulé (le risque n°1 du labo) ; dépendance au modèle
Schwartz de P04 (la forward n'est pas le marché).

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (carry, base, convergence τ=0, **flag simulé**, cohérence P04).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Run MLflow loggué + données DVC.
- [ ] Synthèse `results/` : base théorique, sensibilités, avertissement réel/simulé.
- [ ] Rien écrit hors `core/pricing/derivatives/` + `projects/06_…` (et **pas** `core/pricing/__init__.py`). Commit sur la branche. Ni merge ni push.
