<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# WS — service_product (le véhicule de revenu : produit GPU-prix)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `docs/orchestration/money-parallel-plan.md`,
> `docs/orchestration/instances/WD_compute_benchmark.md`, `private/README.md`,
> `docs/git-workflow.md`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre Git
- **ID** : WS — couche produit (monétisation). **Branche** : `feature/WS-service_product`.
- **Worktree** : `git worktree add ../lab-WS -b feature/WS-service_product integration`
- **Module possédé (écris UNIQUEMENT ici)** : `projects/14_service/`
- **Zone protégée / NON possédé** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml`, tout `core/` (lecture seule).
- **⚠️ Frontière edge** : la PARTIE PUBLIQUE (UI, benchmark, free tier) vit ici. **L'edge** (timing exact « loue maintenant », params calibrés) **reste dans `private/`** (WP) et n'est **jamais** exposé en clair dans le produit public.

## 1. Thèse
Transformer l'actif (benchmark multi-venues + signal de procurement) en un **produit que des gens
paient** : un **dashboard / système d'alertes / API** « le GPU le moins cher en ce moment + tendance
de prix », avec **free tier public** (la mesure) et **valeur premium** (alertes, timing — branché sur l'edge privé).
C'est la pièce qui **convertit les données en revenu** (data-product / abonnement / service).

## 2. Flux de données
Lit le **cold store** réel (`core.storage`) et l'**indice/dispersion** de **WD** (`projects/13_compute_benchmark`)
quand dispo — sinon construit une vue minimale depuis le lac. Le **signal premium** vient de `private/procurement/`
(WP) **par injection** : le produit public ne contient pas la logique d'edge, juste un point de branchement.

## 3. Deux paliers
- **PoC-now** : (a) **dashboard** (Streamlit) « benchmark GPU + venue la moins chère maintenant + courbe de prix
  par modèle » (public, gratuit) ; (b) **squelette d'alerte/API** (« notifie quand H100 < X $ ») avec un point
  d'injection pour le signal privé ; (c) page « méthodo + à propos » (crédibilité = vendabilité).
- **Institutional-target** : abonnements/auth, API monétisée, déploiement (Vercel/Streamlit Cloud), tiers premium branché sur l'edge.

## 4. Architecture (SOLID / DI)
`SignalSource` (Protocol) : le produit consomme un *signal de procurement* **injecté** — implémentation publique
« naïve » (moins cher brut) par défaut, implémentation **privée** (WP) substituée localement (jamais committée).
Vue/produit = couche I/O isolée ; calculs de benchmark = lecture pure du cold store.

## 5. Code à faire grossir
- **Dans `projects/14_service/`** : `dashboard/app.py` (Streamlit), `src/views.py` (lecture cold store/benchmark),
  `src/alerts.py` (squelette + point d'injection signal), `src/signal_iface.py` (Protocol `SignalSource`), `README.md` (pitch produit).

## 6. Tests-first
(a) la vue benchmark sur fixture → valeurs attendues ; (b) le moteur d'alerte déclenche au bon seuil (signal mocké) ;
(c) **anti look-ahead** dans toute courbe historique ; (d) le produit tourne **sans** l'edge privé (signal naïf par défaut) → DI prouvée.

## 7. Reproductibilité
MLflow non requis (produit, pas recherche) ; mais toute donnée affichée vient du **cold store versionné**.

## 8. CROISSANCE DU LABO (obligatoire)
- **Frontière publique/privée** stricte : le repo public ne doit JAMAIS contenir l'edge (cf. `private/README.md`).
- **Référence** : modèles de pricing data-product / freemium → `literature-scout` / `references/`.
- Handoff convergence : `pyproject` testpaths `projects/14_service/tests` ; `streamlit` déjà en dep.

## 9. Dépendances
- **Amont** : WD (benchmark, idéalement mergé d'abord — sinon vue minimale), P11 (storage), W1/W2 (venues). **Au build** : se contente du cold store + une `SignalSource` mockée.

## 10. Risques & angles morts
**Fuite d'edge** dans le produit public (le risque n°1 — garder le timing/calibration en `private/`) ;
construire un produit avant d'avoir un edge prouvé (assumer : le free tier benchmark a déjà de la valeur seul) ;
sur-ingénierie UI (rester PoC : 1 dashboard + 1 squelette d'alerte).

## 11. Definition of Done (PoC-now)
- [ ] Dashboard benchmark public qui tourne (venue la moins chère + courbe par modèle).
- [ ] Squelette d'alerte avec point d'injection `SignalSource` (naïf public par défaut, edge privé substituable).
- [ ] Tests verts (vue, alerte seuil, anti look-ahead, DI sans edge) ; `ruff`/`mypy core` verts.
- [ ] Aucun edge en clair dans `projects/14_service/`. Commit sur la branche. Ni merge ni push.
