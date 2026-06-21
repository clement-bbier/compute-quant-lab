<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P12 — signals_integration (core/signals + desk câblé)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`,
> les skills `/spread-trading-playbook`, `/backtest-pitfalls`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : P12 — passe d'intégration (Desk réel). **Branche** : `feature/P12-signals_integration`.
- **Worktree** : `git worktree add ../lab-P12 -b feature/P12-signals_integration integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`core/signals/`** (nouveau) + `projects/10_portfolio_execution/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, le reste de `core/` (lecture seule). `projects/02` : **additif uniquement** (réexport), sinon handoff convergence.

## 1. Thèse (le problème à régler)
Le desk **P10** agrège aujourd'hui des signaux **MOCKÉS** : les vrais producteurs ne sont
pas consommables. **Pourquoi** : P09 (`core/models`) et P06 (`core/pricing/derivatives`) sont
dans `core/` (importables), mais **P02 vit dans `projects/02_…`** — dossier au préfixe numérique,
**non importable** comme package Python. P12 applique le principe **PoC → fondation** : promouvoir
les *producteurs de signaux réutilisables* dans **`core/signals/`**, derrière une interface commune,
et **brancher les 3 signaux réels** (mean-reversion P02, basis futures P06, ML P09) dans le desk P10.

## 2. Flux / dépendances vérifiés
Consomme (lecture) : `core.pricing` (P01), `core.pricing.derivatives` (P06), `core.models` (P09),
`core.backtest` (P08, interface `Strategy`/signal). La logique mean-reversion de **P02** (cointégration
+ z-score) est **promue** dans `core/signals/` (réimplémentation canonique OU réexport additif depuis
`projects/02`). Données synthétiques au PoC (pas bloqué par tokens).

## 3. Deux paliers
- **PoC-now** : (a) `core/signals/` avec `SignalProducer` (Protocol) + 3 producteurs réels
  (`MeanReversionSignal`, `FuturesBasisSignal`, `MLEnsembleSignal`), tous **point-in-time** ;
  (b) **câbler P10** : remplacer les 3 mocks de `projects/10/src/signals.py` par ces producteurs
  réels dans `run_desk.py` ; (c) backtest desk sur **vrais** signaux → PnL net + attribution par signal.
- **Institutional-target** : pondération dynamique pilotée par la confiance des signaux, capacité, exécution live.

## 4. Architecture (SOLID / DI)
`core/signals/protocols.py` : `SignalProducer` (Protocol) `signal(view ≤ t) -> position`, **compatible
avec l'interface `Strategy` de P08** → un producteur est directement backtestable. Chaque producteur
enveloppe une brique existante (P02/P06/P09) sans la modifier (Adapter + OCP). Le desk P10 injecte une
liste de `SignalProducer` (mocks → réels) sans changer sa logique de pondération.

## 5. Code à faire grossir
- **Dans `core/signals/`** : `protocols.py`, `mean_reversion.py` (promu de P02), `futures_basis.py`
  (sur P06), `ml.py` (sur P09 `core.models`), `__init__.py`.
- **Dans `projects/10_portfolio_execution/`** : `run_desk.py` + `src/signals.py` câblés sur `core.signals`.

## 6. Tests-first
(a) chaque producteur est **point-in-time** (signal à t sur données ≤ t ; un producteur tricheur
lève via la `GuardedView` de P08) ; (b) parité : le `MLEnsembleSignal` reproduit le signal de P09 ;
(c) le desk tourne sur les **3 vrais** producteurs → PnL net déterministe, attribution exacte
(somme des contributions = PnL brut) ; (d) régression : les tests P10 existants restent verts. pytest.

## 7. Reproductibilité
MLflow via `core.backtest.tracking` (producteurs utilisés, params, seed + SHA + DVC). Seed fixe.

## 8. CROISSANCE DU LABO (obligatoire)
- **Promotion** : `core/signals/` devient la fondation des signaux (réutilisable par un futur optimiseur).
- **Nouveaux employés** : **`risk-validator`** (déjà enregistré) — attaquer le PnL **net** agrégé.
- **Convergence** : `pyproject.toml` testpaths `core/signals/tests` ; si `projects/02` doit réexporter depuis `core/signals`, le signaler.

## 9. Dépendances
- **Amont** : **P02, P06, P08, P09** — tous dans `main`. **Modules core requis** : `core.pricing`, `core.pricing.derivatives`, `core.models`, `core.backtest` (lecture).

## 10. Risques & angles morts
Agréger des signaux **overfittés** (le desk hérite de la fragilité de chaque signal) ; look-ahead lors
de la promotion de P02 (préserver son garde-fou point-in-time) ; casser `projects/02` (rester additif) ;
sur-confiance dans un PnL **brut** flatteur. Le `risk-validator` doit attaquer le **net**.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (point-in-time par producteur, parité P09, desk sur vrais signaux, régression P10).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Backtest desk loggué MLflow (PnL net + attribution + SHA + DVC) sur **3 signaux réels**.
- [ ] Synthèse `results/` : PnL net, contribution par signal, honnêteté (mocks→réels change quoi ?).
- [ ] Rien écrit hors `core/signals/` + `projects/10_…` (et `projects/02` additif/handoff). Ni merge ni push.
