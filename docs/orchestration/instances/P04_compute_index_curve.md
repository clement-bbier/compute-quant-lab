<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# P04 — compute_index_curve

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Ne code
> rien tant que le plan n'est pas validé. Lis d'abord le `CLAUDE.md` racine, ce
> fichier, `docs/git-workflow.md`, `docs/parallel-ops.md`, et le module que tu
> possèdes. Ton livrable de session = un **plan d'implémentation**, pas du code.

## 0. Identité & cadre Git
- **ID projet** : P04 — racine de la couche Fondation (aucune dépendance amont).
- **Branche** : `feature/P04-compute_index_curve`
- **Worktree** : `git worktree add ../lab-P04 -b feature/P04-compute_index_curve integration`
- **Module possédé (écris UNIQUEMENT ici)** : `core/ingestion/` (jambe compute) + `infra/collectors/` + `projects/04_compute_index_curve/`
- **Zone protégée (NE PAS toucher ici)** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, **et `core/pricing/`** (possédé par P01) → tout patch remonte à la convergence.

## 1. Thèse
Le prix du compute n'a **pas d'historique profond** : il faut le **fabriquer**.
P04 construit (a) l'**indice spot compute canonique** à partir de Silicon Data
(réel) et accumule des snapshots marketplace en parallèle, et (b) une **courbe
forward SIMULÉE** pour les futures compute CME *annoncés mais non listés*. C'est le
**produit de données fondateur** dont dépendent P03 (term structure) et P06 (dérivés).

## 2. Flux de données vérifiés
| Source | Réel/Simulé | Unité | Fréquence | Accès |
|---|---|---|---|---|
| Indice spot Silicon Data | **Réel** | $/GPU·h | horaire/journalier, UTC | API payante (dispo) |
| Snapshots Vast.ai / RunPod | **Réel** (accumulé maison) | $/GPU·h | journalier, UTC | API publique → `data/snapshots/` |
| Courbe forward compute | **SIMULÉE** | $/GPU·h par échéance | construite | modèle (cost-of-carry / mean-reversion) seedé sur le spot |

Le brut va dans `data/raw/` (immuable) **via le code du connecteur à l'exécution**,
jamais à la main (hook). La forward est **toujours étiquetée simulée**, jamais servie comme réelle.

## 3. Deux paliers
### 3a. PoC-now (preuve exécutable, qualité desk)
Connecteur Silicon Data dans `core/ingestion/` écrivant le brut puis l'indice propre
en `data/interim/`. Collecteur de snapshots `infra/collectors/gpu_price_snapshot.py`
idempotent (dédup), planifiable. Module de **simulation de courbe forward** dans
`projects/04_compute_index_curve/src/` (isolé de `core/pricing/` possédé par P01).
**Polyglotte dès le PoC** : moteur **Monte-Carlo** de la forward (nombreux chemins)
en **Rust/C++** pour la perf, avec référence Python pour les tests.
### 3b. Institutional-target (cible desk réel)
Indice multi-source réconcilié temps réel, courbe forward calibrée sur signaux de
marché, publication de l'indice comme service, promotion de la forward dans `core/pricing/curve/` (en convergence, après merge de P01).

## 4. Architecture (SOLID / DI)
- `ComputeIndexSource` (Protocol) : `fetch(window)` → injecté (Silicon Data, proxy marketplace).
- `SnapshotStore` (Protocol) : `append(snapshot)`, dédup idempotente.
- `ForwardCurveModel` (Protocol) : `simulate(spot, params) -> Curve` → interchangeable
  (impl Rust perf vs impl Python oracle), sélectionnée par injection.
- L'indice agrège des sources via abstraction → ajouter une marketplace = nouvelle impl, pas de modif du cœur (OCP).

## 5. Code à faire grossir
- **Dans `core/`** : `core/ingestion/compute_index.py`, `core/ingestion/protocols.py`.
- **Dans `infra/collectors/`** : `gpu_price_snapshot.py` (service planifié).
- **Dans `projects/04_compute_index_curve/`** : simulation forward + notebooks + `results/`.
- **Polyglotte** : moteur Monte-Carlo forward en Rust/C++ (justifié par le nombre de chemins).

## 6. Tests-first
(a) Construction de l'indice sur fixture connue ; (b) **idempotence/dédup** du
snapshot ; (c) forward : convergence vers le spot à l'échéance 0, monotonies attendues,
**flag « simulé » présent** ; (d) parité Rust ↔ Python du Monte-Carlo ; (e) anti
look-ahead sur l'indice. pytest, vert avant merge.

## 7. Reproductibilité
DVC versionne `data/raw/` (Silicon Data) et `data/snapshots/`. MLflow logue les
params de simulation forward (modèle, seed, nb chemins) + SHA git. Rejouabilité totale.

## 8. CROISSANCE DU LABO (obligatoire)
- **Nouveaux employés** (via `agent-architect` + `/new-agent`) : candidat **skill**
  `/build-forward-curve` (procédure standard de simulation) ; le `data-engineer` existant suffit pour l'ingestion.
- **Références** (`references/`) : modélisation des courbes forward de commodités
  non stockables (analogie élec) → `literature-scout`.
- **Sources / MCP** : consommer les MCP `gpu-price` et `energy-data` ; documenter la source Silicon Data au registre du `CLAUDE.md` (patch convergence).
- **Skills / rules** : rule « toute série forward porte un flag réel/simulé ».

## 9. Dépendances
- **Amont (projets)** : aucune (racine).
- **Modules core requis** : `core/utils/`, `core/data_quality/` (validation post-ingestion).
- **Externe** : accès Silicon Data, APIs Vast.ai/RunPod, toolchain Rust/C++.

## 10. Risques & angles morts
- **Survivorship** dans les snapshots marketplace (offres disparues).
- **Look-ahead** dans la construction d'indice (révisions a posteriori).
- **Réel vs simulé** : risque majeur de servir la forward simulée comme réelle → flag obligatoire + tests.
- **Gaps** d'historique snapshot (collecte récente) → documenter la profondeur réelle.

## 11. Definition of Done (PoC-now)
- [ ] Tests verts (idempotence, flag simulé, parité Rust/Python, anti look-ahead).
- [ ] `ruff check .` & `mypy core` verts.
- [ ] Run MLflow loggué (params simulation) + données DVC versionnées.
- [ ] Synthèse écrite (sources, plage couverte, profondeur, anomalies).
- [ ] Rien écrit hors `core/ingestion/` + `infra/collectors/` + `projects/04_…`. Prêt à merger.
