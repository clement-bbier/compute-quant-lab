# Projet 02 — Spread Mean Reversion

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo détaillée
> et état : [README.md](README.md). Patches zone protégée : [CONVERGENCE.md](CONVERGENCE.md).

## Thèse spécifique
Si la jambe énergie (ENTSO-E) et la jambe compute (marketplaces GPU) sont **cointégrées**, le
spark spread pricé par **P01** dévie temporairement de son équilibre de long terme puis y revient.
On parie sur ce retour à la moyenne (z-score à bande d'hystérésis), backtesté par le moteur **P08**.

## Modules possédés
- `projects/02_spread_mean_reversion/` uniquement.
- Lecture seule : `core.pricing` (P01), `core.backtest` (P08), `core.ingestion` (jambe compute).
- Interdit : tout `core/`, zone protégée racine → patches [CONVERGENCE.md](CONVERGENCE.md).

## Architecture (SOLID / DI)
- `src/cointegration.py` — protocole complet : ADF/KPSS, Engle-Granger (p-value **MacKinnon** via
  `coint`, pas un ADF brut → anti-spurious), Johansen, demi-vie OU, ré-estimation glissante point-in-time.
- `src/strategy.py` — `MeanReversionStrategy(z_entry, z_exit, lookback)` implémente le `Strategy`
  Protocol de P08 : z-score sur fenêtre ≤ t, bande d'hystérésis (entrée/sortie), reset à t==0.
- `src/data_sources.py` — loaders réels (ENTSO-E + indice compute des snapshots) ; provenance
  `simulated` **obligatoire** (rule `forward-real-simulated`) ; `build_spread` via P01.
- `src/run_backtest.py` — pipeline réel câblé, repli simulé étiqueté, run MLflow reproductible.

## Frontière réel/simulé (non négociable)
`DataProvenance.simulated` est obligatoire (sans défaut) ; un test échoue s'il manque. Le réel
(ENTSO-E + marketplaces) n'est jamais mélangé au simulé sans étiquetage explicite.

## État d'avancement (PoC-now)
- [x] Cointégration complète (EG + Johansen + demi-vie + stabilité glissante), anti-spurious testé
- [x] Stratégie mean-reversion à hystérésis, anti look-ahead (garde-fou P08), déterminisme
- [x] Intégration P01 (pricing du spread) + P08 (backtest) + `core.ingestion` (jambe compute)
- [x] Run MLflow reproductible (params + métriques + SHA + DVC + figure PnL + flag simulé + n_trials)
- [x] 22 tests verts ; `ruff`/`mypy core` verts
- [ ] **Données réelles** : token ENTSO-E (inscription en cours) + accumulation snapshots compute
- [ ] Palier institutionnel (3b) : deflated Sharpe, walk-forward, sizing dynamique, exécution

## Résultats clés
Pipeline validé bout-en-bout sur un jeu **SIMULÉ** (provenance `simulated=True`). ⚠️ Le Sharpe
synthétique est **non crédible** (la stratégie épouse le processus générateur OU) : voir le verdict
adversarial dans [results/SYNTHESIS.md](results/SYNTHESIS.md). Aucun alpha n'est revendiqué tant
que le backtest n'a pas tourné sur données réelles.
