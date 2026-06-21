# P02 — Spread Mean Reversion

Stratégie d'arbitrage de **retour à la moyenne** sur le digital spark spread énergie↔compute.
Du test de cointégration au backtest reproductible, en réutilisant les fondations du labo
(**P01** pricing, **P08** backtest, `core.ingestion` jambe compute).

## Pipeline

```
ENTSO-E (énergie réelle) ─┐
                          ├─► core.pricing.SparkSpreadPricer (P01) ─► spread €/GPU·h
snapshots compute réels ──┘                                            │
                                                                       ▼
            cointegration.py (EG MacKinnon + Johansen + demi-vie + stabilité glissante)
                                                                       │
                                                                       ▼
            strategy.MeanReversionStrategy (z-score hystérésis, ≤ t) ─► core.backtest (P08)
                                                                       │
                                                                       ▼
                                   run MLflow (params + métriques + SHA + DVC + figure PnL)
```

## Modules (`src/`)
| Fichier | Rôle |
|---|---|
| `cointegration.py` | ADF/KPSS, Engle-Granger (**p-value MacKinnon** via `coint`, anti-spurious), Johansen, demi-vie OU, ré-estimation glissante point-in-time. |
| `strategy.py` | `MeanReversionStrategy(z_entry, z_exit, lookback)` — bande d'hystérésis sur z-score ≤ t, reset à t==0. La règle de transition `decide()` est le point de design ajustable. |
| `data_sources.py` | Loaders réels (ENTSO-E `load_energy_entsoe`, indice compute `compute_index_series`) + `DataProvenance` (drapeau `simulated` obligatoire) + `build_spread` via P01. |
| `run_backtest.py` | Pipeline réel câblé, repli simulé étiqueté, run MLflow reproductible. |

## Lancer

```bash
# Prérequis (env du labo) : noyau Rust P08 compilé
uv sync --extra dev
uv run maturin develop -m core/backtest/_loop/Cargo.toml

# Tests (lancement explicite : testpaths à élargir en convergence, cf. CONVERGENCE.md)
uv run pytest projects/02_spread_mean_reversion -q

# Backtest + run MLflow (simulé tant que les données réelles ne sont pas branchées)
uv run python projects/02_spread_mean_reversion/src/run_backtest.py
```

### Brancher les données RÉELLES
- **Énergie** : créer un token gratuit sur <https://transparency.entsoe.eu/> (My Account → demande
  d'accès API, mail à transparency@entsoe.eu, activé ~24 h), puis `ENTSOE_API_TOKEN=…` dans `.env`.
- **Compute** : clé Vast.ai (<https://vast.ai/> → account → API key) dans `VASTAI_API_KEY`, puis
  accumuler via le collecteur `infra/collectors/gpu_price_snapshot.py` (l'historique se construit
  jour après jour ; aucune donnée compute rétroactive n'existe). Alternative profonde : Silicon Data
  SDH100RT (payant, `SILICONDATA_API_TOKEN`, à câbler — cf. CONVERGENCE.md).

`run_backtest.py` détecte automatiquement le réel (token + snapshots présents) et bascule sinon sur
le jeu simulé **étiqueté** `simulated=True`.

## Résultats & pièges
Run de référence sur données **simulées** : Sharpe ≈ 7.70 — **non crédible** (la stratégie épouse le
processus générateur OU). Le backtest valide le *pipeline*, pas un alpha. Verdict adversarial complet
(`/backtest-pitfalls`) et feuille de route avant tout alpha : [results/SYNTHESIS.md](results/SYNTHESIS.md).

## Tests (22, verts)
Cointégration (détection + **rejet** d'un couple non-cointégré, anti-spurious), demi-vie OU,
stabilité point-in-time, signal z-score (entrée/sortie/hystérésis), **anti look-ahead** (garde-fou
P08), déterminisme du backtest, provenance réel/simulé obligatoire.
