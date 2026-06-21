---
name: cointegration-analysis
description: Protocole rigoureux pour tester si deux séries (prix élec et prix compute) sont liées par une relation stable exploitable en arbitrage. À invoquer avant de construire toute stratégie de spread ou de mean-reversion.
---
# Cointegration Analysis

Deux séries peuvent être corrélées par hasard (corrélation fallacieuse) sans relation
durable. La cointégration teste une vraie relation d'équilibre de long terme — c'est le
fondement statistique d'un arbitrage de spread. Ne jamais shorter un spread sans l'avoir testé.

## Protocole

1. **Stationnarité** : tester chaque série brute avec ADF (Augmented Dickey-Fuller) et
   KPSS. Une série de prix est typiquement I(1) (non-stationnaire en niveau, stationnaire
   en différence). Confirmer avant d'aller plus loin.
2. **Test de cointégration** :
   - Engle-Granger (2 séries) : régresser y sur x, tester la stationnarité du résidu (ADF).
     Si le résidu est stationnaire → cointégration.
   - Johansen (≥ 2 séries, plus robuste) : préférer pour estimer le vecteur de cointégration
     et le nombre de relations.
3. **Le spread** = combinaison linéaire stationnaire issue du test. C'est lui qu'on trade,
   pas les prix bruts.
4. **Demi-vie de mean-reversion** : estimer via un modèle d'Ornstein-Uhlenbeck (régression
   du Δspread sur le spread retardé). Une demi-vie courte = signal plus exploitable.
5. **Stabilité** : re-tester sur fenêtres glissantes. Une relation qui n'apparaît que sur
   une période est suspecte. La cointégration peut casser (changement de régime).

## Pièges (déléguer la vérif à risk-validator)
- Cointégration in-sample non vérifiée out-of-sample.
- Look-ahead : le vecteur de cointégration doit être estimé en point-in-time, ré-estimé
  sur fenêtre glissante, jamais sur tout l'échantillon d'un coup.

## Outils
`statsmodels` : `adfuller`, `coint` (Engle-Granger), `coint_johansen` (via vecm).

## Référence
Voir `references/stat-arb/` (Engle-Granger 1987 ; Johansen ; Avellaneda & Lee).
