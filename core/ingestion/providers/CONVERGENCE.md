# W1 — providers_foundation · handoffs convergence

> Ce lot écrit **uniquement** dans `core/ingestion/providers/` (nouveau) + `core/ingestion/gpu_market.py`
> (→ shim). Tout ce qui touche la **zone protégée** (`pyproject.toml`, `.github/`, `.claude/`) ou un
> autre module est listé ici pour la session de convergence — **non appliqué** dans ce worktree.

## 1. CI / `testpaths` (zone protégée — `.github/`, `pyproject.toml`)
Les nouveaux tests vivent sous **`core/ingestion/providers/tests`** (seul emplacement autorisé pour ce
lot). Ils ne sont **pas** ramassés par la CI actuelle ni par `testpaths` :
- **`.github/workflows/ci.yml`** : ajouter `core/ingestion/providers/tests` à la boucle d'isolation
  (`for d in tests core/backtest/tests … core/storage/tests projects/*/tests; do …`).
- (Optionnel) **`pyproject.toml`** `[tool.pytest.ini_options]` : sans objet tant que la CI lance chaque
  dossier en isolation ; ne **pas** mettre plusieurs `core/*/tests` dans un même `testpaths` (collision
  de module `conftest`, cf. note pyproject).

Vérif locale (ce worktree, vert) :
```bash
uv run pytest -q core/ingestion/providers/tests        # 14 passed
uv run pytest -q projects/04_compute_index_curve/tests/test_gpu_market.py   # 4 passed (non-régression)
uv run pytest -q core/storage/tests/test_collector_rewire.py               # 2 passed (collecteur intact)
uv run ruff check . && uv run mypy core                # verts (100 fichiers)
```

## 2. Refactor livré (non destructif)
- `core/ingestion/gpu_market.py` est désormais un **shim** : il ré-exporte `normalize_gpu_model`,
  `parse_vastai_offers`, `fetch_vastai`, `parse_runpod_gpu_types`, `fetch_runpod`, et
  `fetch_live_gpu_prices` délègue au registre `core.ingestion.providers.fetch_all`.
- **Aucun changement de comportement runtime** : même signature `fetch_live_gpu_prices(now=None)`,
  même défaut `utcnow`, même ordre (vastai → runpod), même `RuntimeError` (message verbatim) si rien
  n'est configuré, même `Snapshot`. La collecte live (GitHub Actions) tourne à l'identique.
- **Seul écart, cosmétique** : le `logger.warning` des clés absentes est générique
  (`"VASTAI_API_KEY absent : provider 'vastai' ignoré."`) et émis par le logger
  `core.ingestion.providers` (au lieu de `core.ingestion.gpu_market`). Aucun test n'asserte ce texte ;
  ce n'est pas un contrat de comportement.
- `core/ingestion/__init__.py` (hors module possédé, **non touché**) continue d'importer ses symboles
  depuis le shim : la façade `core.ingestion` reste intacte.

## 3. Dépendances
Aucune nouvelle dépendance (`requests` déjà présent dans `pyproject.toml`). Rien à ajouter au lockfile.

## 4. Aval — vague W2 (1 instance = 1 venue)
La fondation est prête. Ajouter une venue = **3 étapes** (documentées dans
`core/ingestion/providers/__init__.py`) :
1. `core/ingestion/providers/<venue>.py` : `parse_<venue>` (pur) + `fetch_<venue>` (I/O token-gated) +
   classe `<Venue>Provider` (`name`, `required_env`, `fetch(now)`), réutilisant `base.normalize_gpu_model`.
2. Ajouter `<Venue>Provider()` au tuple `PROVIDERS`.
3. Test de parité sous `tests/` + (convergence) clé en **Secrets GitHub** pour le collecteur always-on.

Chaque venue W2 écrit dans son propre fichier → zéro collision de merge.

---

# W2 — providers_connectors · handoffs convergence

> Ce lot écrit **uniquement** dans `core/ingestion/providers/` : 5 modules venue
> (`primeintellect, datacrunch, cudo, hyperstack, tensordock`), le registre `__init__.py`
> (tuple `PROVIDERS` → **7 venues**), et `tests/` (conftest + `test_parsers_w2.py` +
> `test_registry.py`). Rien n'est touché hors module. Vast/RunPod, le shim
> `fetch_live_gpu_prices` et le collecteur sont **inchangés** (non-régression verte).

## W2.0 — Validation live REPORTÉE (worktree sans `.env`)
Le worktree `lab-W2` n'a **pas** de `.env` (clés absentes) → impossible de frapper les API
ici. Les schémas ont été **reconstruits depuis la doc publique** (cf. ci-dessous) et les
parsers testés sur **échantillons réalistes** (unitaires + ruff + mypy verts, sans clé).
**À faire à la convergence** (où les Secrets existent) :
- exécuter `python -m infra.collectors.gpu_price_snapshot` → vérifier que les venues
  actives collectent réellement ;
- pour chaque venue à confiance < haute, **confirmer en live** l'endpoint de prix et la
  forme de réponse, puis ajuster le parser si besoin (le contrat de test fige l'échantillon).

## W2.1 — Niveau de confiance + points à confirmer en live
| Venue | Auth | Endpoint prix | Confiance | À confirmer en live |
|---|---|---|---|---|
| **primeintellect** | Bearer `PRIMEINTELLECT_API_KEY` | `GET /api/v1/availability` | **haute** (schéma verbatim) | `prices.onDemand` est-il **par offre** (÷ `gpuCount`, hypothèse retenue) ou déjà par GPU ? |
| **datacrunch** | OAuth2 `CLIENT_ID`/`CLIENT_SECRET` | `GET /v1/instance-types` | **haute** (champs SDK stables) | forme de `/v1/instance-availability` pour enrichir la **région** |
| **cudo** | Bearer `CUDO_API_KEY` | `GET /v1/vms/machine-types` | moyenne | endpoint exact + enveloppe `{machineTypes:[…]}` + `gpuPriceHr.value` (chaîne) ; variante per-data-center |
| **hyperstack** | header `api_key` | `GET /v1/core/flavors` | moyenne | `price_per_hour` **par flavor** (÷ `gpu_count`, hypothèse) vs déjà par GPU ; sens de `stock_available` ; ⚠️ `.env.example` note un **401** (régénérer la clé) |
| **tensordock** | Bearer `TENSORDOCK_API_KEY` | `GET /api/v2/hostnodes` | plus basse | enveloppe v2 **liste ou mapping/id** (helper `_hostnodes_records` tolère les deux) + emplacement exact de `specs.gpu.price`. Bearer = `TENSORDOCK_API_KEY`, **pas** `API_AUTHORIZATION` |

## W2.2 — ⭐ Champs RICHES disponibles par venue (capter = edge futur)
Le `Snapshot` actuel est minimal (`price, gpu_model, lease_type, availability`). Les venues
exposent bien plus — **capté et documenté ici**, pas encore émis (schéma à enrichir, cf. W2.3) :

| Venue | région / DC | mémoire GPU | vCPU | RAM | disque | spot | détail provider |
|---|---|---|---|---|---|---|---|
| primeintellect | `region`,`dataCenter`,`country` | `gpuMemory` | `vcpu.defaultCount` | `memory.defaultCount` | `disk` | **émis** (`isSpot`) | **émis** via `source=primeintellect:<provider>` |
| datacrunch | via `/instance-availability` | `gpu_memory.size_in_gigabytes` | `cpu.number_of_cores` | `memory.size_in_gigabytes` | `storage.size_in_gigabytes` | **émis** (`spot_price_per_hour`) | — |
| cudo | `dataCenterId` | `gpuMemoryGib` | (`vcpuPriceHr`) | (`memoryGibPriceHr`) | — | — | — |
| hyperstack | `region_name` | — | `cpu` | `ram` | `disk` | — (`/stocks` pour dispo fine) | — |
| tensordock | `location.{country,region,city}` | `vram` | `cpu.amount` | `ram.amount` | `storage.amount` | — | — |

## W2.3 — Proposition d'enrichissement de schéma (zone protégée, **non appliqué**)
Pour exploiter le riche, ajouter des champs **optionnels** (rétrocompat) à
`core.ingestion.protocols.Snapshot` **et** `core.storage.schema` :
`region: str | None`, `gpu_memory_gb: int | None`, `vcpu: int | None`, `ram_gb: int | None`,
`disk_gb: int | None`, `provider_detail: str | None` (sous-provider d'un agrégateur, en
alternative au préfixe `source`). Chaque parser remplirait alors les colonnes du tableau W2.2.
À porter par la session de convergence (touche `core/ingestion/protocols.py` + `core/storage/`).

## W2.4 — Dédup agrégateur Prime Intellect
Prime Intellect agrège **plusieurs providers sous-jacents** → `source` est qualifiée
`primeintellect:<provider>` pour éviter de masquer une venue branchée en direct. **Risque** :
double comptage au niveau de l'indice (ex. `primeintellect:datacrunch` chevauche la venue
`datacrunch` directe). **Reco convergence** : stratégie de préférence **direct > agrégateur**
(ou exclusion ciblée dans `build_spot_index`), tracée par `source`.

## W2.5 — Secrets & CI
- **Secrets GitHub** (collecteur always-on) : ajouter `PRIMEINTELLECT_API_KEY`,
  `DATACRUNCH_CLIENT_ID`, `DATACRUNCH_CLIENT_SECRET`, `CUDO_API_KEY`, `HYPERSTACK_API_KEY`,
  `TENSORDOCK_API_KEY` (déjà listés dans `.env.example`). Dès qu'une clé est posée, le
  registre key-gated prend la venue **automatiquement** (aucune autre couche ne change).
- **CI / `testpaths`** : les tests W2 vivent dans `core/ingestion/providers/tests` — **même
  dossier que W1** → la note CI de W1 (§1) couvre déjà l'ajout de ce dossier à la boucle
  d'isolation ; **aucun nouveau chemin** à déclarer (`test_parsers_w2.py` + ajouts conftest/
  registre sont ramassés avec le dossier).

## W2.6 — Vérif locale (ce worktree, vert)
```bash
uv run pytest -q core/ingestion/providers/tests                 # 21 passed
uv run pytest -q projects/04_compute_index_curve/tests/test_gpu_market.py  # 4 (non-régression)
uv run pytest -q core/storage/tests/test_collector_rewire.py    # 2 (collecteur intact)
uv run ruff check . && uv run mypy core                         # verts (106 fichiers)
```
