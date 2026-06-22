<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# W1 — providers_foundation (refactor pluggable des marketplaces)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/orchestration/money-parallel-plan.md`,
> `docs/git-workflow.md`, `docs/parallel-ops.md`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : W1 — fondation (ENABLER de la vague venues). **Branche** : `feature/W1-providers_foundation`.
- **Worktree** : `git worktree add ../lab-W1 -b feature/W1-providers_foundation integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`core/ingestion/providers/`** (nouveau) + `core/ingestion/gpu_market.py`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, le reste de `core/`, `infra/`. Patch → convergence.

## 1. Thèse (pourquoi)
Aujourd'hui Vast.ai et RunPod sont **dans un seul fichier** `core/ingestion/gpu_market.py`.
Pour ajouter N venues **en parallèle sans collision**, il faut un **paquet pluggable** :
1 fichier par venue + un protocole + un registre. Objectif : **ajouter une venue = créer
un nouveau fichier** (OCP), sans toucher au cœur. C'est ce qui débloque la vague W2 et
muscle le benchmark (actif n°1) et le procurement (revenu n°1).

## 2. Refactor cible (NON DESTRUCTIF)
```
core/ingestion/providers/
  __init__.py        # registre : PROVIDERS = [...], fetch_all(now) key-gated
  base.py            # Protocol GpuPriceProvider : name ; env_keys ; fetch(now)->list[Snapshot]
  vastai.py          # extrait de gpu_market : normalize + parse_vastai_offers + fetch_vastai
  runpod.py          # extrait : parse_runpod_gpu_types + fetch_runpod
core/ingestion/gpu_market.py  # SHIM : re-exporte les symboles publics (compat) +
                              # fetch_live_gpu_prices delegue au registre providers
```
- `fetch_live_gpu_prices(now)` **garde sa signature et son comportement** (le collecteur
  `infra/collectors/gpu_price_snapshot.py` et GitHub Actions en dépendent — NE PAS les casser).
- Les fonctions/symboles importés ailleurs (`normalize_gpu_model`, `parse_vastai_offers`,
  `parse_runpod_gpu_types`) restent importables depuis `core.ingestion.gpu_market` (ré-export).

## 3. Architecture (SOLID / DI)
`GpuPriceProvider` (Protocol) : `name: str`, `required_env: tuple[str, ...]`,
`fetch(now) -> list[Snapshot]`. Chaque venue = une classe/impl. Le **registre**
(`providers/__init__.py`) liste les providers ; `fetch_all(now)` n'appelle que ceux dont
la clé est présente (sinon log warning + skip, comportement actuel). Ajouter une venue =
nouveau fichier + 1 ligne dans le registre.

## 4. Tests-first
(a) **parité** : `parse_vastai_offers` / `parse_runpod_gpu_types` donnent **exactement** les
mêmes `Snapshot` qu'avant (réutiliser/raccrocher les tests existants de
`projects/04_compute_index_curve/tests/test_gpu_market.py`) ; (b) le registre **skip** un
provider sans clé ; (c) `fetch_live_gpu_prices` agrège les providers actifs (mock réseau) ;
(d) **les imports existants** (`from core.ingestion.gpu_market import …`) **restent valides**.

## 5. Reproductibilité / non-régression
Aucun changement de comportement runtime : même `fetch_live_gpu_prices`, même collecteur,
même schéma `Snapshot`. La collecte live (Vast+RunPod) doit continuer à marcher à l'identique.

## 6. CROISSANCE DU LABO (obligatoire)
- Ce refactor est la **fondation** que W2 (1 instance/venue) consomme : documenter dans
  `providers/__init__.py` « comment ajouter une venue » (3 étapes).
- Handoff convergence : si `infra/collectors/` ou `pyproject` doit bouger, le **signaler** (CONVERGENCE.md), ne pas l'éditer.

## 7. Dépendances
- **Amont** : aucune. **Aval** : W2 (venues), WP (procurement), WD (benchmark) en dépendent.
- **Externe** : aucune nouvelle (`requests` déjà là).

## 8. Risques & angles morts
**Casser la collecte live** (le bien le plus précieux : elle tourne en prod via Actions) →
garde-fou = test de parité + `fetch_live_gpu_prices` inchangé. Casser des imports existants →
ré-export shim. Sur-abstraire → garder simple (Protocol + registre, rien de plus).

## 9. Definition of Done (PoC-now)
- [ ] `core/ingestion/providers/` : base + vastai + runpod + registre ; `gpu_market.py` shim compatible.
- [ ] Tests verts : parité Vast/RunPod, skip sans clé, agrégation, imports compat.
- [ ] `ruff check .` & `mypy core` verts.
- [ ] `python -m infra.collectors.gpu_price_snapshot` collecte toujours (vérif locale si clés présentes).
- [ ] Rien écrit hors `core/ingestion/providers/` + `core/ingestion/gpu_market.py`. Commit sur la branche. Ni merge ni push.
