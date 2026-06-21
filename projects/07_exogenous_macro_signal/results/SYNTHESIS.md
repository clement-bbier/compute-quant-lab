# P07 — Synthèse : signal macro exogène (lead sur le spread)

> Données **SIMULÉES** (repli déterministe, seed fixe) : démonstration de
> méthode point-in-time, pas une prétention de réalisme. Connecteur réel
> météo/gaz = item `data-engineer` (cf. CONVERGENCE).

## Lead observé
- Meilleure feature : **gas_price_lag0**
- Lead optimal : **2 jour(s)** (le DGP injecte un lead de 3 j).
- |corrélation| au lead : **0.651**

## Confirmation OLS (split temporel strict, pas de shuffle)
- coef = -0.0035, p-value = 3.72e-45
- R² in-sample = 0.457, **R² out-of-sample = 0.346**
- n_train = 328, n_test = 141

## Pièges look-ahead couverts
- Lag de publication explicite (knowledge_ts = value_ts + lag) — test rouge.
- Révisions tardives : seul le millésime publié à temps est vu (vintages).
- Alignement / fuseau UTC tz-aware (rejet du datetime naïf).
- Mesure du lead anti-overfit : cross-corrélation + OLS out-of-sample.

Run MLflow : `d0376bc0c08d4f74960722bf1f14ab2b` — brut exogène DVC : tracked (cache local ; pointeurs `.dvc` gitignorés → committal en convergence, cf. CONVERGENCE).
