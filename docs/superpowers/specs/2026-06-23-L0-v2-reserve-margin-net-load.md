# L0-v2 — Amendement du prédicteur de marge de réserve (ERCOT)

> **Statut : SIGNÉ le 2026-06-23 (session pilote).** Amende le §3 de
> [L0](2026-06-23-L0-ercot-grid-stress-preregistration.md). **Seul le prédicteur de
> marge de réserve change** ; tout le reste de L0 (label spike RTM, lag 18h J-1,
> métrique PR-AUC threshold-free, split purged+embargo, budget 4 specs / BH, baseline
> climatologique, politique Uri) est **INCHANGÉ**.

## Motif (découvert à l'implémentation sur données réelles)

La marge de réserve v1 = `capacité prévue − charge prévue (brute)` à `as_of = 18h J-1`.
Au backfill de l'été 2022, le dataset hébergé `ercot_load_forecast` s'avère être un
produit **court terme** (~1 h d'horizon, granularité 5 min) : au cutoff 18h J-1 il **ne
couvre pas encore le jour J**. Diagnostic point-in-time confirmé :

| Jambe (au cutoff 18h J-1) | Couvre le jour J ? |
|---|---|
| capacité disponible (STSA, 7 j) | ✅ |
| net-load prévu (7 j) | ✅ |
| **charge brute (`ercot_load_forecast`, court terme)** | ❌ |

La prévision de **charge 7 jours** est un autre dataset hébergé, **non backfillé** (quota
free épuisé). La v1 est donc non calculable en l'état.

## Amendement (§3 — prédicteur de marge de réserve)

Marge de réserve prévue = **`capacité disponible (STSA) − net-load prévu`** à
`as_of = 18h J-1` (au lieu de `capacité − charge brute`).

**Justification méthodologique** : le **net-load** (demande − génération renouvelable)
est précisément la charge que la **capacité dispatchable doit servir**. `capacité −
net-load` mesure la **tension réelle du réseau** de façon plus fidèle que `capacité −
charge brute`, qui ignore l'apport renouvelable côté offre. L'amendement est donc à la
fois une *contrainte de disponibilité de données* **et** un raffinement défendable.

Le **second prédicteur** (gradient net-load) et le **label** (spike RTM) sont inchangés.

## Garde-fous (inchangés de L0)

Point-in-time strict (`publish_time <= as_of`, garde-fou `_latest_known_per_interval`),
purged + embargo, PR-AUC threshold-free, Benjamini-Hochberg sur le budget de specs, run
MLflow + SHA git + version DVC. **Retour possible à la v1** (charge brute) si le dataset
de prévision de charge 7 jours est câblé (quota / tier payant).
