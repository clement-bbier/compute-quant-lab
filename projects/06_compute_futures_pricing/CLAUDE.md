# Projet 06 — Compute Futures Pricing (théorique)

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo
> détaillée et lancement : [README.md](README.md). Patchs convergence : [CONVERGENCE.md](CONVERGENCE.md).

## Thèse spécifique
Les futures compute (CME, settlement sur l'indice Silicon Data SDH100RT) sont
**annoncés mais non listés** (revue réglementaire). P06 les **price théoriquement** :
modèle de cost-of-carry `F = S·e^{(r−y)τ}`, base `F − S`, sensibilités (à r, y, τ),
à partir du spot compute réel (P04) et de la courbe forward SIMULÉE (P04, Schwartz).
Edge : être prêt à valoriser la base le jour du listing.

## Modules possédés
- `core/pricing/derivatives/` (nouveau sous-paquet) · `projects/06_compute_futures_pricing/`.
- Interdit : `core/pricing/__init__.py` et fichiers P01, zone protégée racine. → patches convergence.

## Architecture (SOLID / DI)
- **Contrats** (`derivatives/protocols.py`) : `CarryModel` (source de forward, drapeau
  `simulated` dans le contrat), `FuturesPricer` (orchestrateur → `FuturesQuote`).
- **Cœur** (`derivatives/carry.py`) : `carry_forward`, `implied_convenience_yield`
  (inverse), `carry_sensitivities`, `CostOfCarryModel`. Fonctions pures.
- **Cotation** (`derivatives/futures.py`) : `FuturesQuote` (`simulated` OBLIGATOIRE),
  `CarryFuturesPricer` — infère **toujours** le yield implicite de la forward injectée.
- **Adapter** (`src/p04_forward_adapter.py`, couche projet) : branche la forward
  Schwartz P04 dans `CarryModel` (conversion années→jours), `simulated=True`.

## Frontière réel/simulé (non négociable)
`FuturesQuote.simulated` est obligatoire (sans défaut), comme `Curve.simulated` chez P04.
Tout output P06 est `simulated=True` : futures non listés. Spot = réel (`core.ingestion`)
ou repli d'hypothèse **loggué**. Tests dédiés garantissent l'invariant (drapeau + cohérence).

## État d'avancement (PoC-now)
- [x] Cœur cost-of-carry : forward, base, yield implicite, sensibilités (fonctions pures, typées)
- [x] `FuturesQuote` à drapeau `simulated` obligatoire + `CarryFuturesPricer` (DI)
- [x] Adapter forward P04 (cohérence carry ↔ Schwartz testée point par point)
- [x] Démo `run_pricing.py` : spot réel (repli loggué), term structure, run MLflow rejouable
- [ ] Brancher le spot réel (snapshots accumulés) et calibrer la forward sur l'indice réel
- [ ] Palier institutionnel : surface multi-échéances, calendar spreads, options sur futures

## Résultats clés
Base théorique générée bout-en-bout sur 4 échéances (carry exogène + forward P04),
yield implicite extrait de la forward Schwartz, run MLflow rejouable (params + SHA git +
DVC). 19 tests verts. Détails : [README.md](README.md). ⚠️ THÉORIQUE/SIMULÉ.
