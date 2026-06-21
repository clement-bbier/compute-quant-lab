# Projet 01 — Digital Spark Spread Model

> Contexte LOCAL. Le glossaire et les conventions globales sont dans le CLAUDE.md racine.

## Thèse spécifique
Calculer au jour le jour la rentabilité théorique d'un datacenter (prix du compute vs
coût énergétique) pour détecter quand le compute est sur- ou sous-évalué, et en tirer
des signaux d'arbitrage énergie ↔ compute.

## Données
- Énergie : prix spot ENTSO-E (FR/DE), €/MWh, UTC.
- Compute : prix de location H100 (Vast.ai / RunPod), €/h/GPU.

## Pipeline visé
1. Ingestion (core.ingestion) → data/raw/
2. Quality check (/data-quality-check) → data/processed/
3. Features point-in-time + modèle de prédiction élec J+7 (XGBoost)
4. Génération de signaux (core.pricing.spark_spread)
5. Backtest (/run-backtest) sur 2025 → results/
6. Dashboard Streamlit (dashboard/) : courbe réelle vs prédite, PnL cumulé, Sharpe.

## État d'avancement
- [x] Module de pricing du spark spread (core/pricing) + tests
- [ ] Connecteur ENTSO-E
- [ ] Connecteur prix GPU
- [ ] Modèle de prédiction
- [ ] Backtest 2025
- [ ] Dashboard

## Résultats clés
_(à remplir)_
