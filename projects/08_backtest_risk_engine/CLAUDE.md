# Projet 08 — Backtest & Risk Engine

> Contexte LOCAL. Le glossaire et les conventions globales sont dans le CLAUDE.md racine.

## Thèse spécifique
Fondation de confiance du labo : un moteur de backtest **point-in-time, reproductible,
polyglotte** avec un **garde-fou anti look-ahead** qui *échoue* dès qu'un signal à t
consomme une donnée > t. Tout projet de stratégie (P02, P09, P10…) s'y branche. Rend
exécutable la convention « tout backtest loggué MLflow + SHA git + version DVC ».

## Architecture (deux phases)
1. **Phase 1 (Python, guardée)** : à chaque t, `GuardedView(data, t)` → `strategy.signal()`
   → tableau de positions. Le garde-fou look-ahead vit ici (testé en rouge).
2. **Phase 2 (Rust, obligatoire)** : `backtest_loop.accumulate(positions, prices, fees, slippage)`
   → PnL / returns / turnover / trades sur l'historique long. Oracle Python pur =
   `core/backtest/reference_loop.py` (parité bit-exacte).

## Reproductibilité
Chaque run logge MLflow : params + métriques (PnL, Sharpe, max DD, turnover, hit ratio)
+ SHA git + version DVC + figure PnL. Déterminisme garanti (seed loggée, ordre fixe).

## État d'avancement (PoC-now ✅)
- [x] Métriques de risque (Sharpe annualisé, max drawdown, turnover, hit ratio)
- [x] Garde-fou look-ahead (test rouge : une strat trichant via `at(t+1)` fait lever le run)
- [x] Modèle de coûts (frais + slippage) injecté
- [x] Boucle d'accumulation Rust + parité bit-à-bit avec l'oracle Python
- [x] Moteur deux phases + tracking MLflow (params + métriques + SHA + DVC + figure)
- [x] Démo reproductible sur fixtures synthétiques

## Résultats clés
Démo (`run_demo.py`, mean-reversion z-score sur série synthétique, 512 obs, frais 10 bps
+ slippage 5 bps) — run MLflow reproductible :
- PnL total ≈ 0.115 · **Sharpe ≈ 0.62** (réaliste, aucun drapeau overfitting) · max DD ≈ -4.7 %
- turnover ≈ 93.7 · hit ratio ≈ 0.47
- 29 tests verts (métriques analytiques, garde-fou rouge, déterminisme, coûts, parité Rust/Python).

**Limites / pièges couverts** : look-ahead (garde-fou actif + test rouge), coûts explicites,
déterminisme (graine + ordre de sommation fixes), reproductibilité (SHA git + version DVC).
**Hors périmètre (3b)** : deflated Sharpe (seul `n_trials` est tracé), purged/embargoed CV,
multi-actifs, modélisation fine d'exécution.

## Convergence
Patchs zone protégée + items croissance labo : voir [CONVERGENCE.md](CONVERGENCE.md).
