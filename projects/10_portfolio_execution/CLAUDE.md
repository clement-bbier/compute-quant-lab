# Projet 10 — Portfolio & Execution (couche Desk)

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo détaillée
> et état : [README.md](README.md). Patches zone protégée : [CONVERGENCE.md](CONVERGENCE.md).

## Thèse spécifique
Transformer des **signaux** (mean-reversion P02, dérivés P06, ML P09) en un **portefeuille**
qualité desk : pondération sous **budget de risque**, **modèle d'exécution/coûts** réaliste,
**PnL net**. C'est la couche qui répond à « combien on met, et qu'est-ce qu'il reste après frais ».

## Découplage (clé du parallélisme)
P10 ne dépend PAS des entrailles de P02/P06/P09 : il consomme des **signaux génériques** via
l'abstraction `Strategy`/`PointInTimeView` de **P08** (`core.backtest`), avec des producteurs
**mockés** (in-memory). Les vrais se branchent à la **convergence** sans changer le code (OCP).

## Modules possédés
- `projects/10_portfolio_execution/` uniquement.
- Lecture seule : `core.backtest` (P08 : moteur, garde-fou look-ahead, métriques, tracking).
- Interdit : tout `core/`, zone protégée racine → patches [CONVERGENCE.md](CONVERGENCE.md).

## Architecture (SOLID / DI)
- `src/provenance.py` — `SignalProvenance(name, simulated)` : flag `simulated` **obligatoire**
  (rule `forward-real-simulated`). Un test échoue s'il manque.
- `src/signals.py` — `SignalProducer` Protocol + mocks déterministes (`ConstantMock`,
  `MeanReversionMock`, `MomentumMock`) — placeholders P02/P06/P09, bornés [-1, 1], point-in-time.
- `src/portfolio.py` — pondération **inverse-vol** (`inverse_vol_weights`) derrière une
  abstraction `WeightScheme` (seam OCP → `ERCScheme` risk-parity en institutionnel) ;
  `PortfolioConstructor` : vols planchées + écrêtage de levier brut → position nette.
- `src/execution.py` — `ExecutionModel` : coûts **linéaires + impact quadratique** `κ·Δpos²`
  (espace rendement, convention P08) ; terme linéaire en parité avec `LinearCostModel`.
- `src/desk.py` — `DeskStrategy` : `Strategy` composite injectée dans P08 ; fond N signaux en
  une position nette, estime la vol réalisée **point-in-time**, mémorise l'attribution par signal.
- `src/run_desk.py` — pipeline desk → backtest P08 (brut) → coûts → PnL net → run MLflow.

## Frontière réel/simulé (non négociable)
Tous les signaux du PoC sont **mockés** ⇒ `simulated=True` ; la série de prix desk est
**synthétique étiquetée**. Aucun PnL n'est vendu comme alpha (cf. [results/RISK_REVIEW.md]).

## État d'avancement (PoC-now)
- [x] Pondération inverse-vol + budget de risque + seam ERC (OCP), plancher de vol, gross cap
- [x] Modèle d'exécution linéaire + impact quadratique, parité oracle P08
- [x] `DeskStrategy` composite anti look-ahead (garde-fou P08), déterminisme, attribution exacte
- [x] Run MLflow reproductible (params + métriques **nettes ET brutes** + SHA + DVC + figure PnL net)
- [x] 37 tests verts ; `ruff`/`mypy core` verts
- [ ] **Vrais signaux** P02/P06/P09 (convergence) ; agent `risk-validator` (absent, zone protégée)
- [ ] Palier institutionnel : optimiseur risk-parity contraint, capacité, limites desk, exécution live

## Résultats clés
Pipeline validé bout-en-bout sur **signaux mockés** + série **simulée**. PnL **net −0.54** vs
**brut −0.15** : les coûts (frais+slippage+impact κ=0.02) quasi **quadruplent la perte** —
illustration directe de « les coûts d'exécution sont le tueur de PnL » (§10). Aucun alpha
revendiqué : voir [results/SYNTHESIS.md](results/SYNTHESIS.md) et le verdict adversarial dans
[results/RISK_REVIEW.md](results/RISK_REVIEW.md).
