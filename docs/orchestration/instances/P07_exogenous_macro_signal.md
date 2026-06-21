<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P07 — exogenous_macro_signal

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`,
> la rule `.claude/rules/quant-no-lookahead.md`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : P07 — couche Stratégie (features exogènes). **Branche** : `feature/P07-exogenous_macro_signal`.
- **Worktree** : `git worktree add ../lab-P07 -b feature/P07-exogenous_macro_signal integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`core/features/`** + `projects/07_exogenous_macro_signal/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, le reste de `core/` (lecture seule).

## 1. Thèse
Des variables **exogènes** — prix du gaz, météo (HDD/CDD), annonces de buildout datacenter —
précèdent les mouvements de la jambe énergie et de la demande compute, donc du **spark spread**
(P01). P07 construit ces features **point-in-time** dans `core/features/` et teste leur pouvoir
prédictif (lead) sur le spread.

## 2. Flux de données vérifiés
**Nouvelles sources exogènes** (gaz, météo, capacity) via API ; le spread cible vient de
`core.pricing` (P01). ⚠️ Les données macro sont **publiées avec retard et révisées** : modéliser
le **lag de publication** (knowledge-timestamp), sinon look-ahead garanti.

## 3. Deux paliers
- **PoC-now** : ingérer 1–2 variables exogènes (ex. gaz + HDD/CDD), construire des **features
  point-in-time** dans `core/features/`, mesurer corrélation/lead avec le spread (sans sur-fitter).
- **Institutional-target** : nowcasting, modèle causal, panel de variables, gestion des révisions.

## 4. Architecture (SOLID / DI)
`core/features/` : `protocols.py` (`ExogenousSource`, `FeatureBuilder`), `builders.py`
(features point-in-time : lags, moyennes mobiles, **toutes ≤ t**). `FeatureBuilder` pur,
injectable. Le **lag de publication** est un paramètre explicite par variable (défaut conservateur).

## 5. Code à faire grossir
- **Dans `core/features/`** : `__init__.py`, `protocols.py`, `builders.py` (briques réutilisables
  par P09 ML et les autres stratégies).
- **Dans `projects/07_exogenous_macro_signal/`** : `src/sources.py` (I/O API), `src/run_signal.py`, `results/`.

## 6. Tests-first
(a) **anti look-ahead STRICT** : une feature à t n'utilise aucune donnée dont le
knowledge-timestamp > t (test avec lag de publication) ; (b) alignement temporel / fuseau ;
(c) une révision tardive n'écrase pas une feature historique ; (d) builders sur fixtures connues. pytest.

## 7. Reproductibilité
MLflow (variables, lags de publication, fenêtres + SHA + DVC) via `core.utils.tracking`. DVC pour le brut exogène.

## 8. CROISSANCE DU LABO (obligatoire)
- **Sources/MCP** : brancher météo/gaz (registre `CLAUDE.md` §3 « Marchés gaz/météo » → patch convergence) ; `energy-data` pour le contexte.
- **Nouveaux employés** : `data-engineer` pour les connecteurs exogènes ; `risk-validator` sur le look-ahead.
- **Références** : drivers énergie (gaz, météo), datacenter buildout → `literature-scout`.

## 9. Dépendances
- **Amont** : **P01** (spread cible). Alimente **P09** (ML) en aval.
- **Modules core requis** : `core.pricing` (lecture), `core.utils` (config/logging/tracking).
- **Externe** : API gaz/météo (tokens → `.env`, `.worktreeinclude`).

## 10. Risques & angles morts
**Look-ahead MAJEUR** (données macro retardées/révisées) — risque n°1 ici ; corrélation
**spurieuse** (beaucoup de variables, peu d'historique compute) ; survivorship des séries macro ;
data snooping. Le `risk-validator` doit attaquer chaque feature.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (**anti look-ahead avec lag de publication**, alignement, révisions, builders).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Run MLflow loggué + brut exogène versionné DVC.
- [ ] Synthèse `results/` : lead observé, pouvoir prédictif, pièges look-ahead couverts.
- [ ] Rien écrit hors `core/features/` + `projects/07_…`. Commit sur la branche. Ni merge ni push.
