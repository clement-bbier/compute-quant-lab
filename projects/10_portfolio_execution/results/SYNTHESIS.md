# P10 — Synthèse du backtest desk (PoC-now)

> Run MLflow `158c9380…` · `simulated=True` · seed 42 · 1500 pas (pas journalier, 252/an).
> Signaux : `carry_mock`, `mean_reversion_mock`, `momentum_mock` (placeholders P02/P06/P09).
> Pondération **inverse-vol** (lookback 60, plancher 1e-4, gross cap 1.0). Exécution :
> frais 10 bps + slippage 5 bps + impact κ=0.02.

## 1. Ce qui est validé (le livrable réel du PoC)
Le **pipeline desk** de bout en bout est correct et testé (37 tests verts) :
- pondération sous budget de risque (inverse-vol) avec plancher de vol et écrêtage de levier ;
- modèle d'exécution explicite (linéaire + impact convexe), **en parité** avec l'oracle P08 ;
- agrégation via une `Strategy` composite injectée dans le moteur P08, **anti look-ahead** (garde-fou) ;
- **PnL net = brut − coûts** et **attribution exacte par signal** (Σ contributions = PnL brut) ;
- run MLflow reproductible (params + métriques nettes/brutes + figure + SHA + DVC).

## 2. Métriques (brut vs net)
| Métrique | Brut | Net |
|---|---:|---:|
| PnL total (capital=1) | −0.1532 | **−0.5410** |
| Sharpe (annualisé) | −0.495 | **−1.692** |
| Max drawdown | −0.174 | −0.542 |
| Turnover | 86.51 | 86.51 |
| Hit ratio | 0.491 | 0.459 |
| Trades | — | 1499 |

**Lecture** : le brut est déjà ~nul/négatif (les mocks n'ont aucun edge), et les coûts
**quasi quadruplent la perte** (−0.15 → −0.54). C'est l'illustration directe du risque §10 :
*les coûts d'exécution sont le tueur de PnL*. Un desk se juge au **net**, jamais au brut.

## 3. Contribution par signal (PnL brut)
| Signal | Contribution | Commentaire |
|---|---:|---|
| `mean_reversion_mock` | +0.3668 | porteur sur cette série (oscillation OU) |
| `carry_mock` | +0.0441 | biais directionnel constant, marginal |
| `momentum_mock` | −0.5641 | détracteur — paie le bruit de la série |
| **Somme** | **−0.1532** | = PnL brut total (attribution exacte ✓) |

L'inverse-vol n'« annule » pas le momentum perdant : il pèse les signaux par leur vol, pas par
leur performance attendue (il n'en connaît aucune). D'où l'intérêt d'un **risk-parity
corrélation-aware** (seam ERC) au palier suivant.

## 4. Sensibilité au coût d'impact κ
| κ | PnL net | Sharpe net | Coût total |
|---:|---:|---:|---:|
| 0.00 | −0.2830 | −0.910 | 0.130 |
| 0.01 | −0.4120 | −1.310 | 0.259 |
| 0.02 | −0.5410 | −1.692 | 0.388 |
| 0.05 | −0.9281 | −2.706 | 0.775 |
| 0.10 | −1.5732 | −3.903 | 1.420 |

Le PnL net est **monotone décroissant** en κ (testé). Même à κ=0 (coûts purement linéaires) le
net reste négatif : confirmation que **les mocks n'ont pas d'alpha**. Le turnover élevé (86.5 →
~1 trade/jour) rend la stratégie hyper-sensible aux coûts — un signal à fort turnover doit
porter un edge proportionnel.

## 5. Limites (à lever en convergence)
- **Signaux mockés** : aucun alpha revendiqué. Le résultat négatif est la *baseline honnête*.
- **Inverse-vol ignore les corrélations** entre signaux (risque de sur-confiance composite) → ERC.
- **Une seule série synthétique** : pas de test multi-régime ni d'univers GPU évolutif (survivorship).
- **Impact constant** (κ fixe) : pas de dépendance à la liquidité/au notionnel réel → capacité.
- Le branchement P02/P06/P09 et la collecte CI des tests sont des tâches **convergence** (CONVERGENCE.md).

## 6. Reproduire
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml --release
uv run python projects/10_portfolio_execution/src/run_desk.py   # → results/last_run.json + mlruns/
```
