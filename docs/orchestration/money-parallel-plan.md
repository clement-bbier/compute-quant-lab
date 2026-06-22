# Plan parallèle — améliorer le repo & dégager de l'argent

> **Statut : BROUILLON à relire par l'instance suivante avant exécution.**
> Objectif : faire avancer en parallèle (worktrees disjoints) ce qui (a) renforce
> l'actif de données / benchmark et (b) ouvre des revenus réels — **sans jamais
> exposer l'edge** (le repo est public).

## 0. Politique de versionnement (NON négociable)

| Couche | Visibilité | Où |
|---|---|---|
| **Infrastructure** (ingestion, pricing, index, backtest, storage) | **PUBLIC** | `core/`, `projects/` |
| **Benchmark** (indice multi-venues, dispersion, dashboards de démo) | **PUBLIC** (vitrine / vendable) | `projects/` |
| **Edge monétisable** (signaux gagnants, params calibrés, strat tradable) | **PRIVÉ** | `private/` (gitignoré) + `*.private.*` |

Règle : *« est-ce que voir ce fichier fait perdre un avantage ? »* → oui = **`private/`**.
Cf. [`private/README.md`](../../private/README.md). Un signal gagnant committé en public = **edge mort**.

## 1. Les flux de travail (worktrees disjoints)

| ID | Flux | Module possédé (disjoint) | Lien argent | Dépend de | Visib. |
|---|---|---|---|---|---|
| **W1** | **Fondation providers** : `gpu_market.py` → paquet `providers/` (1 fichier/venue) + protocole + registre. Extraire Vast/RunPod. | `core/ingestion/providers/` + `core/ingestion/gpu_market.py` | *enabler* du benchmark | — | public |
| **W2·x** | **Connecteur par venue** (Lambda, TensorDock, DataCrunch, Hyperstack, Genesis…). 1 instance = 1 venue. | `core/ingestion/providers/<venue>.py` | benchmark + procurement | **W1** | public |
| **WP** | **Signal de procurement** (le revenu le plus direct) : « où/quand louer le moins cher » + **backtest des € économisés**. | **`private/procurement/`** | €€ direct (perso/service) | W1, ≥3 venues | **PRIVÉ** |
| **WD** | **Produit benchmark** : packager l'indice multi-venues + dispersion + dashboard de démo (vitrine vendable / portfolio). | `projects/13_compute_benchmark/` | data-product + carrière | W1, W2 | public |
| **WI** | **Infra & repo** : alerte stockage (faite), polish README/portfolio, (plus tard) migration stockage objet. | `.github/`, `README.md`, `docs/` | garde l'actif vivant + carrière | — | public |

**Disjonction vérifiée** : chaque flux possède un dossier/fichier distinct → **zéro collision de merge**, parallélisable.

## 2. Ordre d'exécution
1. **W1 d'abord** (séquentiel) : sans le refactor `providers/`, les connecteurs collisionnent. Merge avant la vague.
2. **Puis en parallèle** : W2·x (autant de venues que de clés dispo), WD, WI, WP (dès ≥3 venues réelles).
3. **Convergence** habituelle : rebase, tests, risk-validator, merge → `main`. Les nouvelles clés → **Secrets GitHub** (pour le collecteur always-on).

## 3. Décisions à trancher (par l'instance suivante / le directeur)
- **Quelles venues** brancher en W2 (bornées par les clés obtenables) ? → cf. table candidats dans le chat. *Confirmer venue par venue.*
- **Combien d'instances** en parallèle ?
- **WP privé** : périmètre exact du signal de procurement (économies vs simple ranking) + métrique (€ économisés).
- **WD** : indice public « de démo » (dégradé) vs réservé ? Décider quelle granularité est publiable sans donner l'edge.
- Seuil de l'alerte stockage (700 Mo par défaut) et déclencheur d'une **migration DVC/stockage objet** (demande d'approbation avant tout changement cloud).

## 4. Alerte stockage (déjà en place)
`.github/workflows/storage-alert.yml` : check hebdo de la taille du repo ; si > 700 Mo, **ouvre une issue → GitHub t'envoie un mail** (`clementbarbier08109@gmail.com` si tes notifications issues sont actives — défaut). Aucun secret requis.
> Vérifier une fois : GitHub → Settings → Notifications → s'assurer que les issues du repo t'emaillent.

## 5. Commandes worktree (après validation du plan)
```bash
# Fondation d'abord :
git worktree add ../lab-W1 -b feature/W1-providers_foundation integration
# Puis, en parallele (exemples) :
git worktree add ../lab-W2-lambda -b feature/W2-provider_lambda     integration
git worktree add ../lab-WD        -b feature/WD-compute_benchmark   integration
git worktree add ../lab-WP        -b feature/WP-procurement_private integration   # produit du PRIVÉ
```
> Chaque instance reçoit un prompt dédié (à générer après revue de ce plan), pensé
> pour `core/ingestion/providers/<venue>.py` ou son module, tests-first, clé-gated.

## 6. Garde-fous rappelés
- Rien d'edge en public (`private/`). Le collecteur always-on (GitHub Actions) tourne déjà.
- 1 worktree = 1 module possédé. Zone protégée (`CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`) → convergence seulement.
- Aucun changement de **stockage cloud** (migration DVC/objet) sans approbation explicite.
