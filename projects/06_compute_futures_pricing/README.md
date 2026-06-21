# P06 — Compute Futures Pricing (théorique / simulé)

Pricing **théorique** des futures compute (CME, settlement sur l'indice Silicon Data
SDH100RT, **non listés**) : base spot/forward et sensibilités, prêts à valoriser le
jour du listing. Voir la spec locale : [CLAUDE.md](CLAUDE.md).

> ⚠️ **THÉORIQUE/SIMULÉ.** Les futures compute ne sont pas listés. Toute forward
> provient d'un modèle (cost-of-carry ou Schwartz P04), jamais d'un marché observé.
> Chaque `FuturesQuote` porte un champ `simulated` obligatoire ; ne jamais présenter
> ces chiffres comme un prix réel.

## Modèle

### Cost-of-carry
Prix forward d'un sous-jacent portant un coût de financement `r` et un convenience
yield `y` (annualisés), à maturité `τ` (années) :

```
F = S · e^{(r − y)·τ}        base = F − S
```

- **Report (contango)** si `r > y` (base positive), **déport (backwardation)** si `y > r`.
- **Convergence** : `F(τ=0) = S`.
- **Sensibilités** (dérivées premières analytiques) : `∂F/∂r = F·τ`,
  `∂F/∂y = −F·τ`, `∂F/∂τ = F·(r−y)`.

### Convenience yield implicite (le pivot)
Le yield `y` n'est **pas observable**. On l'infère en inversant la forward :

```
y = r − ln(F/S) / τ
```

`CarryFuturesPricer` infère **systématiquement** ce yield depuis la forward injectée.
Conséquence : pour un `CostOfCarryModel(r, y)` exogène, l'inversion **redonne `y`**
(round-trip) ; pour la forward **Schwartz simulée de P04**, elle **extrait** le yield
implicite — un seul cadre pour deux dynamiques (carry géométrique vs mean-reversion).

## Architecture

| Élément | Emplacement | Rôle |
|---|---|---|
| `CarryModel`, `FuturesPricer` | `core/pricing/derivatives/protocols.py` | Contrats (DI / SOLID) |
| `carry_forward`, `implied_convenience_yield`, `carry_sensitivities`, `CostOfCarryModel` | `core/pricing/derivatives/carry.py` | Cœur (fonctions pures) |
| `FuturesQuote`, `CarryFuturesPricer` | `core/pricing/derivatives/futures.py` | Cotation + orchestrateur |
| `P04ForwardAdapter` | `src/p04_forward_adapter.py` | Pont vers la forward Schwartz P04 |
| `run_pricing.py` | `src/run_pricing.py` | Démo bout-en-bout + MLflow |

L'adapter P04 vit dans la **couche projet** (pas dans `core/`) pour ne pas coupler le
cœur à `projects/04` : `core` ignore les projets, `mypy core` reste propre.

## Lancer

```bash
uv sync --extra dev
# Démo : spot réel (repli loggué si pas de snapshot), term structure, run MLflow
uv run python projects/06_compute_futures_pricing/src/run_pricing.py
# Sortie : results/futures_pricing_summary.json (+ run sous experiments/mlruns)

# Tests (hors testpaths tant que la convergence n'a pas patché pyproject.toml)
uv run pytest projects/06_compute_futures_pricing/tests
```

## Reproductibilité
Run MLflow (`p06_compute_futures_pricing`) loggant params (spot + source réel/hypothèse,
`r`, `y`, params Schwartz, grille d'échéances, `simulated=True`), métriques (base et
yield implicite par échéance), SHA git et version DVC (via `core.utils.tracking.run`).
Oracle analytique déterministe (pas de Monte-Carlo) → résultat rejouable.

## Limites & angles morts
- Futures **non listés** → 100 % théorique.
- **Convenience yield** non observable : hypothèse (carry exogène) ou inféré (forward P04).
- Dépendance au modèle Schwartz de P04 : **la forward n'est pas le marché**.
- Spot réel non encore accumulé (snapshots) → la démo retombe sur une hypothèse loggée.
