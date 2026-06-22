<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# W2 — providers_connectors (5 venues, schémas VÉRIFIÉS)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `core/ingestion/providers/__init__.py` (le registre
> + « comment ajouter une venue »), `docs/git-workflow.md`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : W2 — élargit le benchmark. **Branche** : `feature/W2-providers_connectors`.
- **Worktree** : `git worktree add ../lab-W2 -b feature/W2-providers_connectors integration`
- **Module possédé (écris UNIQUEMENT ici)** : `core/ingestion/providers/` (5 nouveaux fichiers + le registre `__init__.py`).
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, le reste de `core/`, `infra/`. → patch convergence.

## 1. Thèse
W1 a posé le paquet pluggable `providers/` (Vast/RunPod). W2 ajoute **5 venues confirmées**
(clés testées en live), 1 fichier/venue, enregistrées dans le registre → le collecteur
always-on + l'indice les prennent **automatiquement** (secrets GitHub déjà set).

## 2. Schémas API VÉRIFIÉS (testés HTTP 200 le 2026-06-23 — ne pas re-chercher l'auth)
- **Prime Intellect** ⭐ (AGRÉGATEUR) : `GET https://api.primeintellect.ai/api/v1/availability`,
  header `Authorization: Bearer $PRIMEINTELLECT_API_KEY`. Renvoie des GPU de **plusieurs providers** →
  mapper `source` sur le provider sous-jacent si exposé, sinon `"primeintellect:<provider>"`.
- **DataCrunch / Verda** : OAuth2. `POST https://api.datacrunch.io/v1/oauth2/token`
  json `{"grant_type":"client_credentials","client_id":$DATACRUNCH_CLIENT_ID,"client_secret":$DATACRUNCH_CLIENT_SECRET}`
  → `access_token` ; puis `GET .../v1/instance-availability` (ou `/v1/instance-types` pour le catalogue+prix) en Bearer.
- **CUDO** : `GET https://rest.compute.cudo.org/v1/...` header `Authorization: Bearer $CUDO_API_KEY`
  (auth OK sur `/v1/auth` ; trouver l'endpoint machine-types/prix : `/v1/data-centers/.../machine-types` ou équivalent).
- **Hyperstack** : `GET https://infrahub-api.nexgencloud.com/v1/core/stocks` header `api_key: $HYPERSTACK_API_KEY`
  (a aussi `/v1/core/flavors` pour le détail prix). Renvoie la dispo GPU par région.
- **TensorDock** : `GET https://dashboard.tensordock.com/api/v2/hostnodes` header
  `Authorization: Bearer $TENSORDOCK_API_KEY` (c'est `TENSORDOCK_API_KEY` le Bearer, pas `API_AUTHORIZATION`).

Chaque connecteur **confirme en live** l'endpoint exact de **prix** et la forme de réponse avant de figer le parser.

## 3. Architecture (suivre W1)
1 fichier `providers/<venue>.py` par venue = `parse_<venue>(payload, now) -> list[Snapshot]` (PUR, testé) +
`fetch_<venue>(...)` (I/O) + classe `<Venue>Provider(GpuPriceProvider)` (`name`, `required_env`, `fetch`).
Ajouter chaque venue au registre `PROVIDERS` de `__init__.py`. **Key-gated** : sans clé → skip (warning).

## 4. ⭐ Capturer RICHE (pas juste le prix) — c'est l'edge futur
Capter **tout ce que l'API expose** : **région/datacenter**, **specs** (VRAM, vCPU, RAM, disque), **lease-type**
(on-demand vs **spot/interruptible**), **profondeur de stock**. Le `Snapshot` actuel est minimal
(`price, gpu_model, lease_type, availability`) → **handoff convergence** : proposer l'enrichissement du schéma
`core.ingestion.protocols.Snapshot` + `core.storage.schema` (champs `region`, `gpu_memory_gb`, `vcpu`, … optionnels).
En attendant : remplir ce que le schéma permet + **documenter les champs riches disponibles par venue** (CONVERGENCE.md).

## 5. Tests-first
Pour chaque venue : (a) **parser** sur un **échantillon réel** de la réponse (capturé en live, anonymisé) →
Snapshots attendus ; (b) le registre **skip** la venue sans clé ; (c) `fetch_live_gpu_prices` agrège toutes les
venues actives (mock réseau). **Non-régression** : Vast/RunPod inchangés, collecteur live OK.

## 6. CROISSANCE DU LABO
- Handoff convergence : enrichissement schéma `Snapshot` (§4) ; `pyproject` si une dép venue manque (peu probable, tout en `requests`).
- Documenter dans `__init__.py` les 7 venues actives.

## 7. Dépendances
- **Amont** : W1 (providers/, dans `main`). **Externe** : `requests` (déjà là).

## 8. Risques & angles morts
Casser la collecte live (le bien précieux) → garde-fou non-régression Vast/RunPod + `fetch_live_gpu_prices` inchangé.
Mauvais endpoint prix (confirmer en live). Aggrégateur Prime Intellect : éviter de **doublonner** une venue déjà
branchée en direct (dédup par `source` au niveau index, documenter).

## 9. Definition of Done (PoC-now)
- [ ] 5 connecteurs (`primeintellect, datacrunch, cudo, hyperstack, tensordock`) + registre à jour.
- [ ] Tests verts (parsers sur réponses réelles, skip sans clé, agrégation) ; non-régression Vast/RunPod.
- [ ] `ruff check .` & `mypy core` verts ; `python -m infra.collectors.gpu_price_snapshot` collecte les venues actives.
- [ ] CONVERGENCE.md : champs riches dispo par venue + proposition d'enrichissement schéma.
- [ ] Rien hors `core/ingestion/providers/`. Commit sur la branche. Ni merge ni push.
