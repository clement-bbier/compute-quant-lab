# L0 — Fiche de pré-enregistrement : stress réseau ERCOT → spike RTM

> **Statut : SIGNÉE le 2026-06-23 (session pilote / convergence).**
> Document figé. Toute modification d'une hypothèse, d'un prédicteur, d'un seuil
> ou d'une métrique après cette date ouvre une **nouvelle** fiche L0 — jamais un
> avenant. C'est le contrat anti-p-hacking que les Worktrees A et B référencent.

## 0. Objet et cadrage honnête

On teste si la **prévision ex ante de tension du réseau ERCOT** (connue la veille
au soir) prédit les **événements de rareté soutenus** du marché temps-réel (RTM)
le lendemain, **au-delà** d'une climatologie saisonnière naïve.

**Ce que cette fiche est** : une validation de pipeline point-in-time + une mesure
de skill prédictif sur une relation **quasi-structurelle** (le mécanisme ORDC lie
mécaniquement réserves et prix de rareté). Le résultat dé-risque la machinerie
énergie et calibre l'effet.

**Ce que cette fiche n'est PAS** : une revendication d'alpha nouveau. L'alpha
visé — élec → dislocation du prix compute — est le **cross-leg différé**, gaté sur
l'accumulation du cold store. Il n'est pas testé ici.

## 1. Hypothèses

- **H1 (testée)** : le vecteur de prédicteurs de tension réseau prévu à T améliore
  la prédiction des événements de rareté RTM de T+h **strictement au-dessus** du
  baseline climatologique.
- **H0 (nulle)** : aucun gain de skill sur le baseline (PR-AUC du modèle ≤ PR-AUC
  du baseline, intervalle de confiance inclus).

Confirmer H1 **et** réfuter H1 sont **deux succès** : les deux valident le pipeline
et informent la suite.

## 2. Marché et provenance

- **Marché** : ERCOT (Texas).
- **Source** : données **réelles** ERCOT via `gridstatus` (publiques, sans token).
  Tout point simulé porterait un flag `simulated=True` non optionnel (rule
  `forward-real-simulated`). Ici : **100 % réel**.
- **À vérifier par le `data-engineer` à l'ingestion** (sans changer la fiche) : noms
  exacts des rapports ERCOT et leurs **heures de publication réelles**, pour garantir
  le caractère point-in-time du prédicteur.

## 3. Prédicteur (set GELÉ)

Vecteur connu à **~18:00 CPT le jour J-1** (cutoff de décision) :

1. **Marge de réserve prévue** (MW) = capacité prévue − charge prévue, pour les
   heures cibles de J, issue du dernier rapport de prévision ERCOT publié **avant**
   le cutoff.
2. **Gradient de net-load prévu** (dérivée première sur la fenêtre cible) : capte la
   *vitesse* d'effondrement de la marge au coucher du soleil (duck curve).

> **Le set est fermé à ces 2 prédicteurs.** Aucun ajout (« juste encore une feature »)
> sans ouvrir une nouvelle fiche L0. Chaque prédicteur supplémentaire est un degré
> de liberté compté dans le budget de specs (§7).

## 4. Label cible (événement prédit)

- **Définition primaire** : **spike RTM soutenu** = prix RTM **horaire intégré**
  (moyenne pondérée temps sur l'heure) system-wide **> τ**. L'intégration horaire
  filtre par construction le bruit de microstructure 5/15 min (un blip isolé ne
  déclenche pas).
- **Robustesse de durée** : ≥ 2 intervalles de 15 min **consécutifs** > τ.
- **Label secondaire (zonal)** : même définition sur le hub `HB_WEST` (concentration
  datacenter/mining). *Secondaire seulement* : le prédicteur §3 est system-wide ;
  un spike zonal peut venir d'une congestion locale que cette métrique ne capte pas.
  La zonalisation passe en **primaire** quand le mapping instance→hub existera
  (cross-leg différé).

## 5. Seuil τ (définition du spike)

- **Primaire** : prix RTM horaire > **99e percentile conditionnel à l'heure-de-jour**,
  estimé sur fenêtre **trailing causale** (uniquement données connues à t). La
  conditionnalité heure-de-jour neutralise la forme intra-journalière (sinon on
  flague tous les pics de pointe diurnes).
- **Robustesse** : seuil absolu > **$1 500/MWh** (rareté réelle, pas le $250 d'un
  après-midi d'été texan ordinaire).

## 6. Lag et causalité

- Prédicteur connu ~18:00 J-1 → label réalisé sur les heures de J. **Strictement
  causal** : le label ne peut être connu avant le timestamp du prédicteur.
- On cible le **RTM** (et non le DAM) précisément pour cette raison : le DAM de J
  clôture vers 13:30 J-1, *avant* le cutoff 18:00 → l'utiliser serait du look-ahead.

## 7. Évaluation (anti-p-hacking, figé ex ante)

- **Baseline à battre** : climatologie **heure-de-jour × mois** (taux de base
  saisonnier). H1 n'est validée que si le modèle **bat** ce baseline.
- **Métrique primaire** : **PR-AUC sans seuil** + courbe Precision-Recall complète +
  **diagramme de fiabilité** (calibration). Métrique *threshold-free* et *policy-free*
  par choix : la qualité de signal se mesure indépendamment de tout point de
  fonctionnement.
- **PAS d'asymétrie de coût ici.** La fonction de perte asymétrique faux-négatif /
  faux-positif est un **concern de couche Desk** (P10/P12), à **dériver** de
  l'économie réelle (€/MWh d'exposition × économie d'instance), jamais devinée. Hors
  périmètre L0.
- **Split** : chronologique, **purged + embargo** (machinerie P09). Holdout = dernier
  **30 %** chronologique, **figé** avant tout regard. Embargo de **7 jours** autour
  de la coupure.
- **Budget de specs** : **N = 4** spécifications maximum autorisées (les 2 seuils τ ×
  les 2 labels primaire/secondaire). Correction de multiplicité **Benjamini-Hochberg**
  sur ces 4. Toute spec au-delà = nouvelle fiche.
- **Politique outliers (figée)** : **Winter Storm Uri** (fév. 2021) **inclus** dans
  l'échantillon, **plus** une analyse de sensibilité séparée **avec / sans** Uri
  (événement 100-σ qui dominerait tout fit non maîtrisé).
- **Critère de décision** : H1 retenue si, sur le **holdout**, la PR-AUC du modèle
  dépasse la borne haute de l'IC bootstrap (1000 ré-échantillons) de la PR-AUC du
  baseline, sur la spec primaire, après correction BH.
- **Règle d'arrêt** : une fois le holdout évalué sur les 4 specs, **stop**. Pas de
  re-tuning post-holdout. Tout nouveau cycle = nouvelle fiche datée.

## 8. Prior PUE — Worktree A (orthogonal à ce test)

Documenté ici pour traçabilité, mais **n'entre pas** dans le test §1–§7 : le PUE ne
touche que le **pricing** (spread compute−énergie, Worktree A), pas la relation
stress→prix (Worktree B). Rassurant : la 1ʳᵉ validation ne dépend pas du paramètre
le plus incertain.

- **Distribution** : **truncated-normal**, μ=1.45, σ=0.15, **support [1.2 ; 1.8]**
  (respecte PUE ≥ 1 par construction ; Texas centré plus haut pour le refroidissement).
- **Usage** : **prior strict**, jamais mis à jour par les prix observés (interdit de
  fit-to-price). Propagé en **bandes de sensibilité** dans les sorties de pricing.
- **Note de calibrage** : ancrer le centre sur les moyennes publiées (Uptime
  mondiale ≈ 1.55 ; hyperscale ≈ 1.1–1.2 ; hôtes spot hétérogènes → dispersion réelle
  possiblement plus large que σ=0.15 ; à réviser dans une fiche dédiée si besoin).

## 9. Garde-fous hérités (non négociables)

- Point-in-time strict partout (as_of, lags, révisions) — machinerie `core/features`.
- Frontière réel / simulé étiquetée (rule `forward-real-simulated`).
- Tout backtest/calibration loggué MLflow + SHA git.
- Gates obligatoires : `data-quality-auditor` (ingestion) → `backtest-pitfalls` +
  passe `risk-validator` (avant de croire un résultat) → convergence pilote.
