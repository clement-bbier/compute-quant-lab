# P10 — Synthèse du backtest desk (PoC-now, **signaux réels** P12)

> Run MLflow `cfcd48b6…` · `simulated=True` · seed 42 · 1500 pas (pas journalier, 252/an).
> Signaux : **`mean_reversion_p02`, `futures_basis_p06`, `ml_ensemble_p09`** — les **vrais**
> producteurs promus dans `core.signals` (mocks → réels, P12). Pondération **inverse-vol**
> (lookback 60, plancher 1e-4, gross cap 1.0). Exécution : frais 10 bps + slippage 5 bps + impact κ=0.02.

## 1. Ce qui est validé (le livrable réel du PoC)
Le **pipeline desk** tourne désormais sur les **3 signaux réels** sans changer sa logique (OCP) :
- producteurs promus dans `core.signals` derrière `SignalProducer` (compatible `Strategy` P08) ;
- chaque producteur **point-in-time** (preuve par invariance à la falsification du futur, 23 tests `core/signals`) ;
- `MLEnsembleSignal` en **parité exacte** avec l'adaptateur P09 ; `FuturesBasisSignal` réellement câblé sur le cost-of-carry P06 (un portage en backwardation inverse le signe) ;
- **PnL net = brut − coûts** et **attribution exacte** (Σ contributions = PnL brut) ;
- run MLflow reproductible (params + métriques nettes/brutes + figure + SHA + DVC).

## 2. Métriques (brut vs net)
| Métrique | Brut | Net |
|---|---:|---:|
| PnL total (capital=1) | +0.5057 | **−4.4654** |
| Sharpe (annualisé) | +1.240 | **−7.118** |
| Max drawdown | −0.0409 | −4.4654 |
| Turnover | 455.0 | 455.0 |
| Hit ratio | 0.529 | 0.271 |
| Trades | — | 1479 |

**Lecture** : le brut est **positif** (+0.51, Sharpe 1.24) — mais sur une série **synthétique
mean-reverting**, c'est un artefact (les signaux épousent le processus générateur), **pas de
l'alpha**. Le **net s'effondre à −4.47** : avec un turnover de 455, les coûts d'exécution ne
*quadruplent* plus la perte, ils la **dynamitent**. Verdict desk inchangé : on juge au **net**.

## 3. « Mocks → réels » : qu'est-ce que ça change ? (honnêteté demandée)
| | Mocks (run précédent) | **Réels (ce run)** |
|---|---:|---:|
| PnL brut | −0.153 | **+0.506** |
| PnL net | −0.541 | **−4.465** |
| Turnover | 86.5 | **455.0** |
| Hit ratio brut | 0.491 | 0.529 |

Deux enseignements **non intuitifs** :
1. **Le brut s'améliore** (−0.15 → +0.51) : les vrais signaux ont une structure qui matche la
   série OU (mean-reversion + ML directionnel) là où les mocks sans état n'avaient aucun edge.
   ⚠️ C'est exactement le piège du **backtest sur simulé** (cf. P02, Sharpe 7.70 non crédible) :
   un brut flatteur sur données synthétiques **ne prédit rien** du réel.
2. **Le net empire** (−0.54 → −4.47) : les vrais signaux **tradent beaucoup plus** (turnover ×5.3 :
   hystérésis qui flippe, franchissements de bande ML, momentum de base). Un brut multiplié par
   ~3 mais un turnover multiplié par ~5 ⇒ **les coûts l'emportent**. La leçon §10 (« l'exécution
   est le tueur de PnL ») est **renforcée** par le passage aux signaux réels, pas atténuée.

## 4. Contribution par signal (PnL brut)
| Signal | Contribution | Commentaire |
|---|---:|---|
| `mean_reversion_p02` | +0.2366 | porteur (la série OU **est** mean-reverting par construction) |
| `ml_ensemble_p09` | +0.2253 | porteur (apprend la direction sur le même artefact) |
| `futures_basis_p06` | +0.0437 | marginal (carry momentum, faible sur série stationnaire) |
| **Somme** | **+0.5057** | = PnL brut total (attribution exacte ✓) |

Contrairement aux mocks (momentum **détracteur**), les 3 réels contribuent **positivement** au
brut — mais tous sur le même artefact synthétique. L'inverse-vol pèse par la vol, pas par l'edge :
un **risk-parity corrélation-aware** (seam ERC) reste le bon prochain pas (signaux corrélés ici).

## 5. Sensibilité au coût d'impact κ
| κ | PnL net | Sharpe net | Coût total |
|---:|---:|---:|---:|
| 0.00 | −0.1768 | −0.425 | 0.683 |
| 0.01 | −2.3211 | −4.643 | 2.827 |
| 0.02 | −4.4654 | −7.118 | 4.971 |
| 0.05 | −10.8983 | −9.849 | 11.404 |
| 0.10 | −21.6199 | −10.887 | 22.126 |

PnL net **monotone décroissant** en κ (testé). **Même à κ=0** (coûts purement linéaires), le net
est **déjà négatif** (−0.18) : le seul turnover de 455 suffit à effacer le brut de +0.51. Un signal
à fort turnover doit porter un edge **proportionnel au turnover** — ici il ne l'a pas (et de toute
façon le brut est un artefact synthétique).

## 6. Limites (à lever en convergence / palier institutionnel)
- **Série synthétique** : aucun alpha revendiqué. Le brut positif est un **artefact**, pas un signal de déploiement.
- **Proba ML OOS mais non strictement walk-forward causale** (design assumé de P09) : un pli futur peut entraîner le modèle qui prédit une ligne passée. Au runtime le garde-fou est propre ; la **construction** de la proba ne l'est pas → cible du `risk-validator`.
- **Inverse-vol ignore les corrélations** entre signaux réels (qui sont corrélés ici) → ERC.
- **Turnover non maîtrisé** : pas de pénalité de turnover ni de netting inter-signaux → capacité/exécution live.
- **Un seul régime** : pas de test multi-régime ni d'univers GPU évolutif (survivorship).

## 7. Reproduire
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run pytest core/signals/tests projects/10_portfolio_execution/tests   # 65 verts
uv run python projects/10_portfolio_execution/src/run_desk.py            # → results/last_run.json + mlruns/
```
