# Projet 14 — `service_product` : le véhicule de revenu

> Contexte LOCAL. Glossaire et conventions globales : `CLAUDE.md` racine.
> Cadre d'instance : `docs/orchestration/instances/WS_service_product.md`.

## Thèse

Transformer l'actif (benchmark multi-venues + signal de procurement) en un **produit que
des gens paient** : un dashboard / système d'alertes « **le GPU le moins cher en ce moment
+ tendance de prix** ». **Free tier public** = la *mesure*. **Premium** = la *décision*
(timing calibré), branchée sur l'**edge privé** — jamais exposée en clair.

## Frontière public / edge (règle n°1)

| Couche | Quoi | Où |
|---|---|---|
| **Mesure** (PUBLIC) | qui est le moins cher, à quel niveau, quelle tendance | ce module |
| **Décision** (PREMIUM/edge) | quand louer / sur quelle venue, params calibrés | `private/` (WP), **jamais committé** |

Le produit ne dépend que d'un **Protocol** (`SignalSource`) : l'implémentation publique
par défaut est une **heuristique triviale non-edge** ; l'edge privé la **substitue
localement**. Comme rien de concret-privé n'est importé, la fuite d'edge est
*structurellement* impossible (gardée par `mypy` + un test anti-import).

## Architecture (`src/`)

- **`views.py`** — la *mesure*. Lit le cold store (`core.storage`, injecté via le Protocol
  `SnapshotStore`) et produit une `MarketView` point-in-time (venues retenues triées +
  indice canonique) et une `price_curve`. Indice & anti look-ahead **délégués** à
  `core.ingestion.build_spot_index` (réutilisation, zéro réécriture de `core/`).
- **`signal_iface.py`** — la *frontière*. `Action`, `ProcurementSignal`, `SignalProvenance`
  (drapeau `simulated` **obligatoire**), le Protocol **`SignalSource`** (point d'injection
  unique) et `NaiveSignalSource` (impl publique : `RENT_NOW` ssi la moins chère est sous la
  médiane inter-venues ; sinon `WAIT`).
- **`alerts.py`** — le *squelette d'alerte*. `AlertEngine(source, notifier)` évalue des
  règles déclaratives (`PriceBelow` = publique pure ; `ActionIs` = pilotée par l'edge
  injecté). `Notifier` = stub (mémoire / log) ; la livraison réelle (email/webhook) est
  hors PoC. Déterministe et point-in-time (`fired_at = market.as_of`).

## Dashboard (`dashboard/app.py`)

Vitrine Streamlit (couche I/O pure) : venue la moins chère maintenant, dispersion
inter-venues, courbe de tendance, reco heuristique gratuite (étiquetée non-edge), section
méthodo. Dégrade proprement quand l'historique est maigre.

```bash
streamlit run projects/14_service/dashboard/app.py
```

## Données

Tout vient du **cold store versionné** (`core.storage`, lac Parquet). L'historique compute
n'existe nulle part ailleurs : il s'accumule en continu (collecteur 24/7). Au démarrage le
lac peut être maigre — le produit le gère (messages de dégradation), aucune valeur inventée.

## Tests (`tests/`) — tests-first

| Fichier | Garantie |
|---|---|
| `test_views.py` | venue la moins chère *retenue* + indice canonique sur fixture |
| `test_signal_iface.py` | reco naïve `RENT_NOW`/`WAIT` ; provenance `simulated` obligatoire |
| `test_alerts.py` | déclenchement au bon seuil (signal mocké) ; notifier stub |
| `test_point_in_time.py` | **anti look-ahead** (une obs future n'entre pas dans une mesure passée) |
| `test_di_without_edge.py` | le produit tourne **sans** edge ; edge substituable ; aucun import `private` |

```bash
uv run pytest projects/14_service/tests
```

## État (PoC-now)

- [x] Mesure publique (`views`) sur cold store réel, point-in-time, réutilise `build_spot_index`
- [x] Frontière `SignalSource` + impl naïve publique par défaut (non-edge, `simulated=True`)
- [x] Squelette d'alerte (point d'injection unique, règles déclaratives, notifier stub)
- [x] Dashboard Streamlit (moins chère + dispersion + tendance + méthodo, dégradation propre)
- [x] 28 tests verts ; aucun edge en clair
- [ ] **Handoff convergence** : ajouter `projects/14_service/tests` aux `testpaths` (zone protégée)
- [ ] *Institutional-target* : auth/abonnements, API monétisée, déploiement, premium branché sur l'edge (WP)

## Dépendances

Amont : P11 (`core.storage`), P04 (`core.ingestion.build_spot_index`), W1/W2 (venues), idéalement
WD (`projects/13`) quand mergé (sinon vue minimale depuis le lac — cas actuel). Au build : se
contente du cold store + une `SignalSource` (naïve par défaut). **Rust-free** : le produit ne
tire pas le moteur de backtest.
