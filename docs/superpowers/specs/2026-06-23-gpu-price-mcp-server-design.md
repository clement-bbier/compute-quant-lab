# Design — Serveur MCP `gpu-price`

> Date : 2026-06-23 · Statut : validé en brainstorming, en attente de revue utilisateur
> Auteur : session directeur de recherche (Claude) · Cible : `infra/mcp-servers/gpu-price-server/`

## 1. Contexte & objectif

Le dossier `infra/mcp-servers/gpu-price-server/` ne contient qu'un `.gitkeep` : le serveur
est **déclaré** dans `.mcp.json` (`command: python … server.py`) mais **non implémenté**, donc
il ne démarre ni dans Claude Code ni dans VSCode.

Le collecteur [infra/collectors/gpu_price_snapshot.py](../../../infra/collectors/gpu_price_snapshot.py)
accumule déjà l'historique des prix de location GPU dans `data/snapshots/` (CSV **et** lac
Parquet partitionné, double écriture). **Objectif** : exposer cet historique réel via un
serveur MCP afin qu'un agent (Claude Code, mode agent VSCode) puisse l'interroger en langage
naturel — dernier prix, historique, stats, requête SQL — en respectant le point-in-time.

## 2. Périmètre

**Dans le périmètre**
- 5 outils MCP en lecture seule sur le lac Parquet (`data/snapshots/`).
- Point-in-time (`as_of`) optionnel sur les outils structurés.
- Harnais de tests TDD (logique pure isolée du framework MCP).
- Ajout de la dépendance `mcp` et alignement `testpaths`.

**Hors périmètre**
- Le serveur `energy-data` (lot séparé, dépend du connecteur ENTSO-E).
- L'agrégation indice spot canonique P04 (le serveur sert le **brut**, pas l'indice).
- Tout backend autre que le cold store Parquet (TickStream/HotCache restent des stubs).
- Le mirroir dans le `mcp.json` natif de VSCode (étape suivante, une fois le serveur prouvé).

## 3. Décisions actées (brainstorming)

| # | Décision | Choix retenu |
|---|----------|--------------|
| Q1 | Surface | **Riche** : `latest_price`, `price_history`, `list_gpu_models`, `summary_stats`, `query` (SQL) |
| Q2 | Point-in-time | **`as_of` optionnel partout** (défaut = maintenant) |
| Q3 | Sécurité SQL | **Full DuckDB** via `core.storage.query` (risque assumé, documenté) |
| Archi | Structure | **Approche 1** : serveur mince + service pur testable |
| Consigne | Tests | « bien tester que cela fonctionne » → TDD sérieux, point-in-time prouvé |

## 4. Architecture & composants

Approche 1 — la logique métier est isolée du framework MCP pour être testable sans démarrer
le serveur (respecte « fonctions pures côté core, I/O explicite » de `python-quality.md`).

```
infra/mcp-servers/gpu-price-server/
├── service.py    # Logique PURE : reçoit un PriceStore injecté, renvoie des dicts JSON-sérialisables. AUCUN import mcp.
├── server.py     # FastMCP : 5 @mcp.tool() qui délèguent à service.py + résolution du chemin data/snapshots + transport stdio.
├── tests/
│   └── test_service.py   # TDD : ParquetPriceStore en tmp_path + données synthétiques déterministes
├── README.md     # provenance : unité ($/GPU·h), fuseau (UTC), fréquence (snapshot horaire), réel/simulé
└── CONVERGENCE.md  # handoff zone protégée : pyproject (mcp) + matrice CI (cf. §10), comme W1
```

- **Lecture** : `core.storage.ParquetPriceStore(<racine>)` — `read(as_of=…, source=…)` borne déjà
  au point-in-time et rejette un `as_of` naïf.
- **Résolution de la racine** dans `server.py` : `os.environ["CLAUDE_PROJECT_DIR"]` si présent,
  sinon `Path(__file__).resolve().parents[3]`, puis `/ "data" / "snapshots"`.
- **Injection** : `service.py` ne connaît que le **Protocol** `PriceStore`. Les tests injectent un
  store temporaire ; `server.py` injecte le store Parquet réel. (DI / OCP, patron du labo.)

## 5. API des outils

Toutes les réponses portent `"provenance": "real"` (spot observé réel — règle `forward-real-simulated.md`)
et l'`as_of` **effectif**. Toutes les fonctions `service.py` sont pures : `(store, …) -> dict`.

### 5.1 `list_gpu_models(store, *, as_of=None) -> list[str]`
Liste triée des `gpu_model` distincts présents dans le lac (bornée à `snapshotted_at <= as_of`).

### 5.2 `latest_price(store, gpu_model, *, lease_type="on_demand", as_of=None) -> dict`
Pour chaque `source`, le relevé le plus frais (`max snapshotted_at <= as_of`) du modèle/bail.
```json
{
  "gpu_model": "H100", "lease_type": "on_demand", "as_of": "2026-06-21T13:54:59+00:00",
  "provenance": "real", "found": true,
  "by_source": [{"source": "vastai", "price_usd_per_hour": 2.13, "availability": 4,
                 "snapshotted_at": "2026-06-21T13:54:59+00:00"}],
  "summary": {"min": 2.13, "median": 2.13, "max": 2.13, "n_sources": 1}
}
```
Modèle inconnu → `{"found": false, "message": "...", "available_models": [...]}`.

### 5.3 `price_history(store, gpu_model, *, start=None, as_of=None, source=None, lease_type=None) -> dict`
Série temporelle ordonnée croissante. `as_of` borne le haut (point-in-time), `start` borne le bas.
```json
{"gpu_model": "H100", "start": null, "as_of": "...", "provenance": "real", "n": 42,
 "observations": [{"snapshotted_at": "...", "source": "vastai", "lease_type": "on_demand",
                   "price_usd_per_hour": 2.13, "availability": 4}]}
```

### 5.4 `summary_stats(store, gpu_model, *, lease_type=None, as_of=None) -> dict`
Stats descriptives sur les relevés (bornées au point-in-time).
```json
{"gpu_model": "H100", "as_of": "...", "provenance": "real", "n": 42,
 "overall": {"count": 42, "min": 1.9, "max": 2.4, "mean": 2.11, "median": 2.13, "std": 0.08},
 "by_source": [{"source": "vastai", "count": 42, "min": 1.9, "max": 2.4, "mean": 2.11, "median": 2.13}],
 "first_obs_at": "...", "last_obs_at": "..."}
```

### 5.5 `query(store, sql) -> dict`
Délègue à `core.storage.query(sql, store)` (vue `prices` = le lac). Renvoie les lignes.
```json
{"columns": ["gpu_model", "n"], "rows": [{"gpu_model": "H100", "n": 42}], "n": 1,
 "note": "SQL DuckDB brut — AUCUN garde point-in-time, le filtrage as_of est à la charge de la requête"}
```

## 6. Sémantique point-in-time (anti look-ahead)

- `as_of` reçu en **chaîne ISO** par MCP → parsé en `datetime`. **Naïf rejeté** avec message
  explicite (« fournir un instant tz-aware UTC, ex. `2026-06-21T00:00:00+00:00` »). Cohérent
  avec `ParquetPriceStore.read` et la règle `data-integrity.md`.
- `as_of` absent → « maintenant » = tout l'historique disponible. L'`as_of` effectif renvoyé est
  alors le `max(snapshotted_at)` observé (auditable).
- Les 4 outils structurés bornent à `snapshotted_at <= as_of`. **`query` ne l'applique pas** (lac
  brut) — `note` explicite dans la réponse + README.

## 7. Sécurité (choix assumé : full DuckDB)

- `query` réutilise `core.storage.query` **tel quel** : connexion DuckDB en mémoire, vue `prices`,
  mais **tout le pouvoir DuckDB** reste accessible (`read_csv('C:/…')`, `COPY … TO`, `INSTALL httpfs`).
- **Risque** : le serveur est piloté par un LLM ; une prompt-injection pourrait générer une requête
  destructrice ou exfiltrante. **Décision utilisateur explicite**, tracée dans le README et la
  docstring de l'outil (« n'expose ce serveur qu'à des agents de confiance »).
- **Mitigation différée** (non implémentée, notée pour plus tard) : mode bac-à-sable SELECT-only /
  désactivation de l'accès fichiers. À rouvrir si le serveur est exposé hors poste local.

## 8. Gestion d'erreurs

- `gpu_model` inconnu → réponse `found: false` + `available_models` (pas d'exception : guide le LLM).
- Lac vide → réponses vides/neutres (géré par `ParquetPriceStore.read`).
- `as_of` naïf / ISO invalide → `ValueError` → `server.py` renvoie une erreur d'outil MCP lisible.
- Erreur SQL DuckDB → message propagé dans la réponse de l'outil `query`.

## 9. Données & provenance (README)

| Attribut | Valeur |
|---|---|
| Unité | USD par GPU·heure ($/GPU·h) |
| Fuseau | UTC, tz-aware (datetime naïf interdit) |
| Fréquence | snapshot planifié (horaire, Task Scheduler / GitHub Actions) |
| Sources | marketplaces (vastai, … ; champ `source`) |
| Réel/simulé | **réel** (spot observé) — aucune série simulée servie ici |
| Backend | lac Parquet partitionné `source=/month=` sous `data/snapshots/` (versionné DVC) |

## 10. Dépendances & intégration (zone protégée → convergence)

Branche construite sur `main` post-W1 (`209fab1`). Le serveur est **indépendant de la couche
providers W1** : il lit le storage, n'appelle jamais `fetch_live_gpu_prices` ni les providers.
Les fichiers de la **zone protégée** (`pyproject.toml`, `.github/workflows/ci.yml`) passent **uniquement
par la convergence** (parallel-ops §7) — donc **documentés dans `CONVERGENCE.md`, NON appliqués dans la
branche**, exactement comme W1 :

- **`pyproject.toml`** (handoff) : ajouter `"mcp>=1.2"` aux `dependencies`. Pour le dev/test local,
  `mcp` est installé **ad-hoc** dans le `.venv` (`uv pip install mcp`), comme `duckdb` en P11.
- **`.github/workflows/ci.yml`** (handoff) : ajouter `infra/mcp-servers/gpu-price-server/tests` à la
  **matrice CI** (1 job isolé), comme la convergence W1 l'a fait pour `core/ingestion/providers/tests`.
  **`testpaths` reste `["tests"]`** — on ne le modifie pas (pattern réel du labo confirmé par `209fab1`).
- **`.mcp.json`** : **déjà câblé** (`gpu-price` → `python … server.py`), zone protégée mais aucun
  changement requis ; le serveur démarrera dès le code écrit.

En local, la suite serveur se lance par chemin explicite : `pytest infra/mcp-servers/gpu-price-server/tests`.

## 11. Stratégie de test (TDD)

Tests écrits **avant** le code. `test_service.py` monte un `ParquetPriceStore(tmp_path)`, y écrit
des snapshots synthétiques **déterministes** (≥ 2 sources, ≥ 2 modèles, ≥ 2 instants), puis vérifie :

1. `list_gpu_models` → distincts, triés, bornés par `as_of`.
2. `latest_price` → relevé le plus frais **par source**, résumé min/médian/max exact, respect de `as_of`.
3. `price_history` → ordre croissant, bornes `start`/`as_of`, filtre `source`/`lease_type`.
4. `summary_stats` → count/min/max/mean/median/std exacts sur données connues + ventilation par source.
5. **Point-in-time** : un relevé postérieur à `as_of` est **exclu** (test anti look-ahead dédié).
6. `as_of` naïf → `ValueError` ; `as_of` ISO invalide → erreur claire.
7. `gpu_model` inconnu → `found: false` + `available_models`.
8. `query` → un `SELECT count(*) … GROUP BY gpu_model` renvoie le bon nombre de lignes.
9. **Smoke test** `server.py` : import OK et les 5 outils sont enregistrés dans l'instance FastMCP.

## 12. Critères d'acceptation

- [ ] `pytest infra/mcp-servers/gpu-price-server/tests` vert (intégration au CI = handoff convergence, cf. §10).
- [ ] `ruff check .` et `mypy` verts sur le nouveau code (type hints + docstrings NumPy).
- [ ] Le serveur démarre en stdio et expose 5 outils (vérifié par le smoke test).
- [ ] Une requête manuelle « dernier prix H100 » renvoie une valeur cohérente issue de `data/snapshots/`.
- [ ] Le test point-in-time prouve l'exclusion des relevés postérieurs à `as_of`.

## 13. Suite (hors lot)

- Mirroir des serveurs dans le `mcp.json` natif de VSCode (`${workspaceFolder}`, `envFile`).
- Serveur `energy-data` (ENTSO-E).
- Éventuel mode SQL bac-à-sable si exposition hors poste local.
