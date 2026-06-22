# Serveur MCP `gpu-price`

Expose l'historique **réel** des prix de location GPU (snapshots accumulés dans `data/snapshots/`)
via MCP (stdio). Lecture seule, point-in-time.

| Attribut | Valeur |
| --- | --- |
| Unité | USD par GPU·heure ($/GPU·h) |
| Fuseau | UTC, tz-aware (instant naïf rejeté) |
| Fréquence | snapshot planifié (collecteur `infra/collectors/gpu_price_snapshot.py`) |
| Sources | marketplaces (`source` : vastai, runpod, …) |
| Réel/simulé | **réel** (spot observé) |
| Backend | lac Parquet `core.storage.ParquetPriceStore` sous `data/snapshots/` |

## Outils

- `list_gpu_models(as_of?)` — modèles connus (triés, bornés point-in-time).
- `latest_price(gpu_model, lease_type="on_demand", as_of?)` — dernier prix par source + résumé.
- `price_history(gpu_model, start?, as_of?, source?, lease_type?)` — série temporelle.
- `summary_stats(gpu_model, lease_type?, as_of?)` — count/min/max/mean/median/std + par source.
- `query(sql)` — SQL DuckDB **brut** sur la vue `prices`.

## ⚠️ Sécurité

`query` réutilise `core.storage.query` : **tout le pouvoir DuckDB** (`read_csv`, `COPY … TO`,
`INSTALL httpfs`) reste accessible. Piloté par un LLM, ce serveur peut être détourné par
prompt-injection (écriture/exfiltration de fichiers). **N'exposer qu'à des agents de confiance,
sur poste local.** Aucun garde point-in-time sur `query` (lac brut).
