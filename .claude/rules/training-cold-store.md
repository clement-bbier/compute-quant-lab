---
paths:
  - "core/models/**"
  - "core/features/**"
  - "projects/**"
---
# Entraînement = cold store versionné (jamais le hot store)

- L'entraînement et le backtest lisent **toujours** le cold store **immuable et
  versionné** (Parquet + DVC, cf. `docs/storage-roadmap.md`), jamais un store mutable
  (TimescaleDB / Redis).
- Le hot store (serving temps réel) est réservé à l'**inférence live** / monitoring,
  pas à la reproductibilité d'entraînement.
- Tout run logge la **version DVC** des données (via `core.utils.tracking`) → un modèle
  se ré-entraîne à l'identique. Un dataset non versionné ne sert pas de base d'entraînement.
