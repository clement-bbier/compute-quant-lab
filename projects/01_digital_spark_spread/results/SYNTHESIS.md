# P01 — Synthèse du pricer du digital spark spread

> Run de démonstration du **pricer vectoriel point-in-time** (`core.pricing`).
> Reproductible : `prepare_dataset.py` → `run_pricer.py` (MLflow). Chiffres bruts :
> [`run_summary.json`](run_summary.json).

## 1. Couverture du run

| Élément | Valeur |
|---|---|
| Fenêtre | 2025-01-01 → 2025-01-31 (744 h, UTC) |
| Région / GPU | FR / H100 (8x, TDP 700 W, PUE 1.82) |
| Jambe énergie | **repli synthétique déterministe** (pas de token ENTSO-E en session ; swap réel = 1 fonction) |
| Jambe compute | stub Silicon Data (H100, mean-reverting, ~2.3 $/GPU·h) |
| FX | 0.92 €/$ (constant) |
| Noyau | `PythonOracle` (parité Rust vérifiée bit-à-bit en test) |

**Note d'honnêteté** : le run de démo tourne sur la jambe énergie *synthétique*
(token ENTSO-E absent de l'environnement de session). La voie réelle est codée et
testée (`fetch_energy_entsoe`) ; elle s'activera dès le token fourni, sans autre
changement. Les chiffres ci-dessous illustrent donc la **mécanique**, pas un
edge de marché mesuré sur données réelles.

## 2. Résultats

| Métrique (€/GPU·h) | Valeur |
|---|---|
| Spread moyen | **2.024** |
| Écart-type | 0.110 |
| Min / Max | 1.785 / 2.322 |
| % d'heures positives | **100 %** |
| Revenu moyen (compute) | 2.137 |
| Coût moyen (énergie) | 0.113 |

## 3. Lecture économique

Le coût énergétique marginal d'une heure-GPU (**0.11 €**) ne représente que
**~5,3 %** du prix de location du compute (**2.14 €**). Le digital spark spread
est donc **structurellement large et positif** au régime de prix actuel : louer
du H100 couvre très largement l'électricité consommée (PUE inclus).

Conséquence pour le desk : l'arbitrage énergie↔compute **ne se joue pas** sur le
niveau de la facture élec en régime normal — il faudrait un choc. Le signal
intéressant naîtra (a) d'un **choc énergie** (crise type 2022) ou (b) d'un
**effondrement du prix du compute** (sur-offre de GPU). Le pricer est l'instrument
qui datera ces bascules en point-in-time.

## 4. Sensibilité PUE / puissance / énergie

Prix élec moyen implicite du run ≈ **88,7 €/MWh**. À revenu compute constant :

| Scénario | Coût €/GPU·h | Spread €/GPU·h |
|---|---|---|
| Base (PUE 1.82, 0.7 kW) | 0.113 | 2.024 |
| PUE dégradé 2.5 | 0.155 | 1.982 |
| GPU 1.0 kW (classe Blackwell) | 0.161 | 1.975 |
| Énergie ×5 (~443 €/MWh, crise) | 0.565 | 1.572 |
| **Énergie de breakeven** | = revenu | **≈ 1 677 €/MWh** |

Le spread est **dominé par le prix du compute** : PUE et puissance n'en déplacent
que quelques centimes. Il faudrait une électricité à ~**1 677 €/MWh** (≈ 19× la
moyenne) pour annuler la marge — d'où l'asymétrie ci-dessus.

## 5. Anomalies & edge cases observés (tests)

- **Anti look-ahead** : ajouter des lignes d'index > t laisse le spread à t
  bit-identique ; sur grille compute grossière, l'alignement as-of *arrière*
  renvoie le dernier prix connu (jamais le futur), et **NaN** avant la première
  publication compute (point-in-time strict, pas de fill depuis le futur).
- **Unités/fuseau** : conversion €/MWh → €/GPU·h validée à la main ; FX
  point-in-time ; **datetime naïf rejeté** (UTC tz-aware obligatoire) ; tz non-UTC
  normalisée en UTC.
- **Parité Rust↔Python** : `np.allclose` sur 10 000 points aléatoires (bit-exact).
- **DI** : le pricer tourne sur sources/FX/kernel *mockés* (découplage prouvé).

## 6. Reproduire

```bash
# Données (réel si ENTSOE_API_TOKEN dans .env, sinon repli synthétique)
.venv/Scripts/python.exe projects/01_digital_spark_spread/src/prepare_dataset.py
# Pricing + run MLflow + run_summary.json
.venv/Scripts/python.exe projects/01_digital_spark_spread/src/run_pricer.py
mlflow ui --backend-store-uri experiments/mlruns   # params + métriques + SHA git
```
