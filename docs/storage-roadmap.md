# Roadmap stockage — du fichier au temps réel

> Comment le labo stocke la donnée pour **entraîner des modèles sur un historique
> fiable** aujourd'hui, et **servir du temps réel** demain — sans sur-construire.
> Règle directrice : *le bon stockage dépend de l'usage*, et on n'avance d'une phase
> que quand un **déclencheur** concret le justifie.

## 0. Principe non négociable : reproductibilité d'abord

L'entraînement lit **toujours** le **cold store versionné** (Parquet + DVC), **jamais**
le hot store mutable (TimescaleDB/Redis). Un run MLflow logge la **version DVC** des
données (déjà câblé dans `core.utils.tracking`) → on ré-entraîne à l'identique des mois
plus tard. Le hot store sert le **serving/monitoring**, pas la repro.

```
   COLLECTE → COLD (Parquet+DVC, immuable, point-in-time) → entraînement / backtest
                  └─(stream)→ HOT (Timescale/Redis) ───────→ serving live / dashboard
```

## 1. Réalité data actuelle (point de départ)

| Jambe | Cadence | Historique | Stockage actuel |
|---|---|---|---|
| Énergie (ENTSO-E) | horaire, batch | profond (API) | `data/raw/` + DVC |
| Compute (Vast/RunPod) | snapshot (live) | **inexistant → on l'accumule** | `data/snapshots/*.csv` |
| Forward compute | simulée | — | artefacts projet |

→ Tout est **batch**. Le temps réel n'a de sens que si on crée un flux (Phase 2).

## 2. Couche d'abstraction (à poser AVANT tout backend)

Un paquet `core/storage/` avec des **Protocols** (DI/SOLID), pour que les projets
dépendent d'abstractions, jamais d'un backend concret (même patron que les sources P04) :

- `PriceStore` : `write(frame)`, `read(query, as_of)` → impl Parquet, puis Timescale.
- `TickStream` : `produce(tick)`, `consume()` → impl Redpanda (Phase 2).
- `HotCache` : `set_latest(...)`, `get_latest(...)` → impl Redis (Phase 4).

**Bénéfice** : changer de backend = nouvelle implémentation, **zéro modif** des stratégies/modèles (OCP). La migration entre phases devient indolore.

## 3. Les phases (chacune avec son déclencheur)

### Phase 0 — Cold store : **Parquet + DVC** *(à faire maintenant)*
- Remplacer `CsvSnapshotStore` → **`ParquetSnapshotStore`** : colonne, typé, compressé,
  partitionné (`source` / mois). Append-only, idempotent (dédup conservée).
- **DVC-tracker** `data/snapshots/` (+ `raw/`, `interim/`) → chaque dataset versionné.
- **Fix qualité** au passage : garder la **distribution** des offres par modèle (ne pas
  réduire à 1 ligne/modèle) — l'agrégation (trimmed-mean) appartient à l'indice P04, pas au store.
- **Déclencheur** : c'est le socle, aucun prérequis. **Owner** : `data-engineer`.

### Phase 1 — Couche requête : **DuckDB** *(quand tu veux du SQL)*
- DuckDB lit le Parquet **directement en SQL**, embarqué, **zéro serveur**.
- Usage : EDA, jointures point-in-time à l'échelle, construction de features (P07/P09).
- **Déclencheur** : pandas-sur-fichiers devient pénible, ou besoin de SQL analytique.
- **Owner** : `data-engineer`. Coût quasi nul.

### Phase 2 — Ingestion temps réel : **Redpanda** + tick collector *(le vrai pivot)*
- Transformer le snapshot quotidien en **collecteur de ticks haute fréquence** : poller
  Vast/RunPod toutes les 1–5 min → publier sur un topic `compute.prices` (Redpanda,
  Kafka-compatible, mono-binaire, plus léger que Kafka), via **docker-compose local**.
- Consommateurs : (a) sink **cold** (Parquet/DVC, entraînement), (b) sink **hot** (Phase 3),
  (c) MAJ **Redis** (Phase 4). Le prix GPU **bouge en intraday** → streamer a du sens.
- **Déclencheur** : tu veux de la granularité intraday / un pipeline vivant.
- **Owner** : `infra-engineer` (services/compose/CI) + `data-engineer` (schémas/sinks).

### Phase 3 — Hot historique : **TimescaleDB** (défaut) / ClickHouse *(au volume)*
- TimescaleDB = Postgres + séries temporelles (hypertables, **continuous aggregates**,
  compression). SQL, transactionnel, écosystème riche → **défaut recommandé**.
- Stocke les ticks streamés pour requêtes time-range rapides + agrégats continus
  (OHLC 1 min / 1 h de l'indice compute).
- ClickHouse **seulement** si OLAP massif (≫10⁸ lignes, scans analytiques lourds).
- **Déclencheur** : latence des requêtes sur Parquet/DuckDB qui pique, ou agrégats sur flux.
- **Owner** : `infra-engineer`.

### Phase 4 — Serving / features chaudes : **Redis** *(quand un consommateur live existe)*
- Redis garde le **dernier prix / feature** (+ fenêtres courtes) pour servir en **faible
  latence** : pricer spark spread live, inférence P09, desk P10, dashboard.
- **Déclencheur** : un modèle/dashboard a besoin de l'état courant en sub-seconde.
- **Owner** : `infra-engineer`.

### Phase 5 — Feature store point-in-time *(quand le ML mûrit)*
- Split offline (entraînement, cold) / online (serving, hot) **point-in-time correct**.
- Promouvoir les features de `core/features/` (P07) ici. Éviter le prématuré : les
  jointures point-in-time (déjà faites par P07) sont le cœur ; l'outillage vient après.

## 4. Anti-sur-ingénierie (à lire avant de coder Kafka)

- **Ne pas** monter Redpanda + Timescale + Redis **sur des snapshots quotidiens** : tu
  aurais un moteur de course sans carburant. Le streaming n'a de sens **qu'après** avoir
  décidé de ticker en intraday (Phase 2).
- Rester **Phase 0–1** tant que la donnée est batch et le volume modeste (DuckDB-sur-Parquet
  encaisse beaucoup). **Local-first** : tout en docker-compose ; managed cloud au seul palier institutionnel.
- **Poser l'abstraction (§2) maintenant** : c'est ce qui rend les phases 2–4 indolores le jour venu.

## 5. Comment ça se construit (rituel du labo)

Lot dédié = un projet d'infra données, exécuté dans un **worktree** comme les autres
(plan → tests-first → commit → convergence). Modules possédés : `core/storage/` + `infra/`.
Owners : `infra-engineer` (à fabriquer via `agent-architect`) + `data-engineer`.

**Prochain pas concret recommandé : Phase 0** (`ParquetSnapshotStore` + DVC + fix distribution)
— petit, à fort levier, débloque tout le reste.
