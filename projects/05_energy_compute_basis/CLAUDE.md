# Projet 05 — Energy ↔ Compute Basis

> Contexte LOCAL. Glossaire et conventions globales : CLAUDE.md racine. Méthodo détaillée
> et état : [README.md](README.md). Patch zone protégée : [CONVERGENCE.md](CONVERGENCE.md).

## Thèse spécifique
Le spark spread varie **par région** : prix élec régional (FR/DE, ENTSO-E) × **PUE** local
× efficience matérielle. Le **basis** inter-régions (différence des spreads régionaux, ajustée
PUE) ouvre un arbitrage géographique : placer la charge GPU là où le spread est le plus large.
P05 mesure ce basis point-in-time, quantifie ses dislocations et leur persistance, et expose
honnêtement ses limites.

## Modules possédés
- `projects/05_energy_compute_basis/` uniquement.
- Lecture seule : tout `core/` (P01 `core.pricing`, P04 `core.ingestion`, `core.utils`),
  zone protégée racine. Tout besoin sur la zone protégée → [CONVERGENCE.md](CONVERGENCE.md).

## Architecture (SOLID / DI)
- `RegionConfig` (PUE, FX, efficience) = config injectée, pas de nombre magique.
- `build_regional_pricer(cfg)` → `SparkSpreadPricer` (P01) **par région** (le PUE vit dans le
  `PowerModel`, donc un pricer par région).
- `BasisCalculator(pricers, reference=...)` **pur** : price chaque région, aligne par jointure
  interne (point-in-time), `basis[r] = spread[r] − spread[reference]`.
- `detect_dislocations(basis)` : épisodes `|basis| > seuil` (amplitude p95, fraction du temps)
  + persistance = **demi-vie AR(1)** de retour à la moyenne.
- I/O (ENTSO-E, indice compute P04, MLflow) isolé dans `src/data.py` + `src/run_basis.py` ;
  `src/basis.py` reste pur (aucune I/O cachée).

## Frontière réel / synthétique (non négociable)
Énergie ENTSO-E FR/DE = **réelle** si token, sinon **repli synthétique déterministe** étiqueté.
Indice compute = réel (marketplace P04) ou repli synthétique étiqueté. Aucune série simulée
servie comme réelle ; l'étiquette `energy_source` / `compute_source` est loggée dans MLflow.

## Risques assumés (PoC)
PUE régional = hypothèse forte (peu observable). Compute souvent **global** → le basis est
surtout porté par l'énergie × PUE (le revenu compute s'annule entre régions à FX/compute égaux).
Coûts/latence de transfert ignorés au PoC → ne pas sur-interpréter un arbitrage « gratuit ».

## État d'avancement
- [ ] `RegionConfig` + `build_regional_pricer` (tests)
- [ ] `BasisCalculator` point-in-time (basis multi-région, sensibilité PUE, anti look-ahead)
- [ ] `detect_dislocations` (seuil + demi-vie AR(1))
- [ ] Orchestration `run_basis.py` + run MLflow + `results/SYNTHESIS.md`

## Hors périmètre (palier institutionnel)
Routing de charge optimisé, coûts/latence de transfert, contraintes de capacité, signal
tradable inter-régions exécutable.
