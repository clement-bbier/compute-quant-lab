# P10 — Portfolio & Execution

Couche **Desk** du labo : agréger des signaux en un portefeuille sous budget de risque,
modéliser l'**exécution et les coûts**, et juger la stratégie au **PnL net**.

## Pourquoi cette couche
P01–P09 produisent des *signaux* (spreads, futures, vol, ML…). Aucun ne dit **combien on met**
ni **ce qu'il reste après frais**. P10 répond à ça : c'est la couche qui transforme une
collection de vues en un portefeuille tradable et en mesure le PnL réaliste.

## Découplage & parallélisme
P10 consomme l'abstraction `Strategy` / `PointInTimeView` de **P08** (`core.backtest`). Les
producteurs de signaux sont **mockés** au PoC ; P02/P06/P09 se branchent en convergence derrière
le même Protocol `SignalProducer`, sans toucher au code du desk (OCP). P10 tourne donc **en
parallèle** des projets de signaux.

## Architecture
```
signaux mockés ──► DeskStrategy (Strategy composite P08)
   (s_i ∈[-1,1])      │   à chaque t :
                      │   1. s_i,t via GuardedView ≤ t        (signals.py)
                      │   2. vol réalisée point-in-time        (desk.py)
                      │   3. poids inverse-vol + budget        (portfolio.py)
                      │   4. position nette = clip(Σ w_i s_i)
                      ▼
        moteur P08 (sans coût) ──► rendements BRUTS + positions
                      ▼
        ExecutionModel  ──► coûts (linéaire + κ·Δ²) ──► PnL NET   (execution.py)
                      ▼
        run MLflow : params + métriques nettes/brutes + attribution + figure  (run_desk.py)
```

### Décisions de design
- **Pondération** : inverse-vol `w_i = (b_i/σ_i)/Σ_j(b_j/σ_j)` au PoC, derrière `WeightScheme`
  (seam OCP) qui ouvre la porte au **risk-parity / ERC** (corrélation-aware) en institutionnel.
- **Exécution** : `coût(Δpos) = (frais+slippage)/1e4·|Δpos| + κ·Δpos²`. Le terme linéaire fait
  **parité bit-pour-bit** avec `LinearCostModel`/`reference_loop` de P08 ; le terme quadratique
  modélise un impact convexe (capacité : un gros rebalancement coûte plus que deux petits).

## Anti look-ahead & déterminisme
- Tout ce qui entre dans la décision à `t` vient de la `GuardedView` (≤ t) de P08 : un signal
  qui lit le futur **fait échouer le run** (`LookAheadError`). Testé (`test_desk_lookahead`).
- La vol de pondération utilise des rendements réalisés **laggés** (`s_{t-1}·marché[t]`).
- L'état du desk est réinitialisé à `t==0` → deux runs sur la même série coïncident.

## Reproductibilité
Run MLflow via `core.backtest.tracking.tracked_run` : params (pondération, coûts, κ, signaux,
`n_trials`, `simulated`) + métriques **nettes et brutes** + contribution par signal + figure du
PnL net + SHA git + version DVC. Graine fixée (`SEED=42`). Snapshot `results/last_run.json`.

## Lancer
```bash
# Prérequis : noyau Rust P08 compilé dans le worktree
uv run maturin develop -m core/backtest/_loop/Cargo.toml --release

uv run pytest projects/10_portfolio_execution/tests   # 37 tests
uv run python projects/10_portfolio_execution/src/run_desk.py
```
> ⚠️ `pyproject.toml` `testpaths` pointe la fondation P01 ; lancer les tests P10 par **chemin
> explicite** tant que la convergence n'a pas ajouté `projects/10_…/tests` (cf. CONVERGENCE.md).

## État
PoC validé sur **mocks** (37 tests verts, `ruff`/`mypy core` verts, run MLflow loggué). Le PnL
net est **négatif** : c'est attendu (les mocks n'ont aucun edge) et **honnête**. Détail et
verdict adversarial : [results/SYNTHESIS.md](results/SYNTHESIS.md),
[results/RISK_REVIEW.md](results/RISK_REVIEW.md). Suite : [CONVERGENCE.md](CONVERGENCE.md).
