# P05 — Revue risque (adversaire)

> Rôle « risk-validator » du labo : traquer look-ahead, overfitting, data-snooping et
> l'illusion d'un arbitrage « gratuit » **avant** d'y croire. Verdict tranché par point.

## 1. Look-ahead
Le basis lui-même est point-in-time (jointure as-of arrière dans le pricer, jointure interne
entre régions — aucune valeur future ne fuit, prouvé par `test_no_lookahead_...`). **En
revanche**, `detect_dislocations` calcule le seuil `z·std` sur **toute la fenêtre** (in-sample) :
pour une *mesure descriptive*, acceptable ; pour un *signal tradable*, c'est du look-ahead (à t,
on ne connaît pas l'écart-type futur). **Verdict : OK en PoC descriptif, problème réel dès qu'on
trade.** → seuil expanding/rolling obligatoire.

## 2. Arbitrage « gratuit »
Le revenu compute est **global** (même prix, même FX) : il s'annule, donc
`basis = power_kw·(pue_DE·energy_DE − pue_FR·energy_FR)/1000`. Ce n'est **pas** un spread de
compute inter-régions : c'est un **spread de prix d'électricité pondéré par le PUE**, déguisé.
Coûts/latence/capacité de transfert ignorés. **Verdict : faux arbitrage au PoC** — « placer la
charge là où le spread est large » n'est pas exécutable tant que le transfert n'est pas net.

## 3. Hypothèse PUE
PUE régional en dur (FR=1.20, DE=1.45), non observable. Le **signe et l'amplitude** du basis en
dépendent directement (cf. `test_pue_sensitivity_is_monotone`). Choisir des PUE qui « font »
l'arbitrage = data-snooping. **Verdict : risque réel.** → PUE sourcé + bandes d'incertitude +
basis reporté en fourchette, jamais en point.

## 4. Persistance AR(1)
Sur données **synthétiques** (saisonnalité horaire + bruit i.i.d.), la demi-vie AR(1) mesure
surtout l'autocorrélation du générateur, pas une propriété de marché. La demi-vie observée
**0.23 h (~14 min)** est inférieure à toute latence de transfert/exécution réaliste. **Verdict :
non exploitable** ; chiffre descriptif du générateur, à recalculer sur l'indice réel.

## 5. Overfitting / data-snooping
Approche descriptive (pas de split train/test — acceptable car non prédictif). Mais les
**108 « épisodes »** sont gonflés par le bruit qui re-franchit le seuil (pas de durée minimale ni
d'hystérésis) → compte très sensible au bruit. Une promotion en signal exigerait : fenêtres
multiples, `n_trials` tracé, deflated Sharpe. **Verdict : compte d'épisodes peu robuste en l'état.**

## Garde-fous prioritaires avant tout signal tradable
1. **Seuil & épisodes hors-échantillon** : `std` expanding/rolling + durée minimale / hystérésis
   sur les épisodes (sinon look-ahead + comptage bruité).
2. **PUE sourcé avec incertitude** : remplacer les points par des fourchettes, reporter la
   sensibilité du basis aux bandes PUE ; ne jamais traiter un PUE ponctuel comme vérité.
3. **Nette des coûts de transfert/latence/capacité** + données **réelles** (ENTSO-E + indice
   compute réel) avant de parler d'arbitrage exécutable ; tracer `n_trials` (deflated Sharpe).
