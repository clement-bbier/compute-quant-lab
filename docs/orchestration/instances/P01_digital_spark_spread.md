<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P01 — digital_spark_spread

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Ne code
> rien tant que le plan n'est pas validé. Lis d'abord le `CLAUDE.md` racine, ce
> fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`, et le module que tu
> possèdes. Ton livrable de session = un **plan d'implémentation**, pas du code.

## 0. Identité & cadre Git
- **ID projet** : P01 — racine de la couche Fondation (aucune dépendance amont).
- **Branche** : `feature/P01-digital_spark_spread`
- **Worktree** : `git worktree add ../lab-P01 -b feature/P01-digital_spark_spread integration`
- **Module possédé (écris UNIQUEMENT ici)** : `core/pricing/` + `projects/01_digital_spark_spread/`
- **Zone protégée (NE PAS toucher ici)** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` → tout patch remonte à la convergence.

## 1. Thèse
Une heure-GPU produit un revenu (location, €/h) et consomme un coût (électricité ×
puissance × PUE). La marge instantanée — le **digital spark spread** — est le P&L
fondamental de l'exploitation d'un GPU. L'edge : les deux jambes se cotent sur des
marchés déconnectés (énergie : mature, liquide, historisée ; compute : naissant,
fragmenté), donc le spread est volatil et imparfaitement arbitré. P01 en fait le
**pricer canonique** dont dépend toute la couche stratégie.

## 2. Flux de données vérifiés
| Source | Réel/Simulé | Unité | Fréquence | Accès |
|---|---|---|---|---|
| ENTSO-E spot FR/DE | **Réel** | €/MWh | horaire, UTC | `entsoe-py` + token (`.env`) |
| Indice spot Silicon Data | **Réel** | $/GPU·h (→ €) | horaire/journalier, UTC | API payante (dispo) |
| PUE | Hypothèse | sans dim. | config | `core/utils/config` |
| Puissance GPU (H100/Blackwell) | Hypothèse | W (TDP) | config | `core/utils/config` |
| FX $/€ | Réel | taux | journalier | source à brancher |

Tout I/O passe par `core/` (jamais de chemin en dur). La consommation se fait en
**point-in-time** : le prix compte au timestamp où il était *connu*.

## 3. Deux paliers
### 3a. PoC-now (preuve exécutable, qualité desk)
Un pricer `SparkSpreadPricer` dans `core/pricing/` qui, à partir de séries énergie
et compute alignées (mêmes timestamps UTC), calcule le spread par GPU·h, point-in-time,
avec PUE / puissance / FX **injectés**. Sortie : une série de spread + décomposition
(revenu, coût) sur l'historique. **Polyglotte dès le PoC** : noyau de calcul vectoriel
du spread sur la grille complète (région × temps × type de GPU) en **Rust** (via
`pyo3`/`maturin`), doublé d'une implémentation Python de référence servant d'oracle aux tests.
### 3b. Institutional-target (cible desk réel)
Pricing intraday temps réel multi-région / multi-GPU, surface de marge, intégration
au moteur de risque (P08), calibration FX/PUE dynamique, exposition via service.

## 4. Architecture (SOLID / DI)
- `PriceSource` (Protocol) : `energy_price(t)`, `compute_price(t)` → injecté, mockable.
- `PowerModel` (Protocol) : `draw_watts(gpu)`, `pue()` → injecté.
- `FxConverter` (Protocol) : conversion $/€ point-in-time.
- `SparkSpreadPricer` dépend de ces **abstractions**, pas de leurs implémentations
  (DIP). Le noyau Rust est une implémentation interchangeable du calcul, sélectionnée
  par injection ; la Python reste l'oracle. Testabilité = sources mockées.

## 5. Code à faire grossir
- **Dans `core/`** : `core/pricing/spark_spread.py`, `core/pricing/protocols.py`,
  `core/pricing/power_model.py`, noyau Rust `core/pricing/_kernel/` (build maturin).
- **Dans `projects/01_digital_spark_spread/`** : notebook d'exploration, dashboard
  (déjà amorcé), `src/` spécifique, `results/`.
- **Polyglotte** : jambe Rust = noyau vectoriel du spread (justifié par la taille de
  grille historique). Reste = Python.

## 6. Tests-first
Écrire AVANT le code : (a) maths du spread sur entrées connues (revenu − coût) ;
(b) **anti look-ahead** : le spread à t n'utilise aucune donnée > t ; (c) alignement
unité/fuseau (€/MWh ↔ $/GPU·h, UTC) ; (d) **parité Rust ↔ Python** (oracle) ;
(e) propriété : `spread == revenu − coût`. pytest. Vert obligatoire avant merge.

## 7. Reproductibilité
DVC versionne le dataset énergie+compute aligné. MLflow logue params (PUE, puissance,
FX, fenêtre) + métriques + SHA git. Un tiers rejoue le spread à l'identique depuis
`dvc pull` + le run MLflow.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** (via `agent-architect` + `/new-agent`) : envisager une **rule**
  path-scopée « cohérence d'unités/fuseau » sur `core/pricing/`. Pas d'agent neuf requis.
- **Références** (`references/`) : littérature *spark/dark spread* des marchés de l'énergie
  (transposée au compute) à distiller via `literature-scout`.
- **Sources / MCP** : brancher une source FX ; consommer le MCP `energy-data` existant.
- **Skills / rules** : candidat `/price-spark-spread` si la procédure se standardise.

## 9. Dépendances
- **Amont (projets)** : aucune (racine).
- **Modules core requis** : `core/utils/` (config, logging) en lecture.
- **Externe** : token ENTSO-E, accès Silicon Data, toolchain Rust (`maturin`).

## 10. Risques & angles morts
- **Look-ahead** : prix compute publié avec retard → caler sur le *connu à t*.
- **Unité/fuseau** : €/MWh vs $/GPU·h, UTC vs local → tests dédiés.
- **Sensibilité PUE/puissance** : documenter, analyse de sensibilité.
- **Réel vs simulé** : P01 n'utilise que du **réel** ; ne jamais mélanger avec la
  forward simulée de P04. Le `risk-validator` doit pouvoir attaquer ces points.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (dont anti look-ahead + parité Rust/Python).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Run MLflow loggué (params + métriques + SHA).
- [ ] Données versionnées DVC.
- [ ] Synthèse écrite (couverture, anomalies, edge observé).
- [ ] Rien écrit hors `core/pricing/` + `projects/01_…`. Prêt à merger vers `integration`.
