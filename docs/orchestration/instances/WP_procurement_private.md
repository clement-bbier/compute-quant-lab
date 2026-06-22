<!-- Prompt d'instance focalisée. Auto-suffisant, exécutable en MODE PLAN dans une session vierge. -->

# WP — procurement_private (signal d'achat compute — EDGE, RESTE LOCAL)

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Lis d'abord
> le `CLAUDE.md` racine, ce fichier, `private/README.md`, `docs/orchestration/money-parallel-plan.md`,
> `docs/git-workflow.md`. Livrable = un **plan**, pas du code.

## 0. Identité & cadre — ⚠️ STREAM PRIVÉ (pas le flux git habituel)
- **ID** : WP — revenu direct. **Branche** : `feature/WP-procurement_private` (locale, **jamais poussée**).
- **Worktree** : `git worktree add ../lab-WP -b feature/WP-procurement_private integration`
- **Module possédé (écris UNIQUEMENT ici)** : **`private/procurement/`** (gitignoré) + fichiers `*.private.py`.
- **⚠️ NON NÉGOCIABLE** : **rien de ce que tu produis ici ne doit être versionné/poussé.** Le repo est PUBLIC ; ce signal est l'**edge**. Le `.gitignore` le garantit déjà (`private/**`, `*.private.*`), mais le principe : **TOUT reste local**. Pas de `git add`, pas de merge, pas de push, jamais. Cf. `private/README.md`.

## 1. Thèse (le revenu le plus direct)
« **Quelle venue et quel moment** pour louer une GPU-heure au **moins cher** » — avec le
**backtest des € réellement économisés**. C'est exploitable **dès aujourd'hui** : tu agis dessus
(louer perso) ou tu le vends comme service. L'edge = la **décision** (timing/routing), pas la mesure.

## 2. Flux de données
Lit le **cold store** réel (`core.storage.ParquetSnapshotStore` — snapshots Vast/RunPod accumulés
24/7). Réutilise `core.ingestion` (public) pour normaliser. Tu **consommes** le code public, tu ne
le modifies pas ; ta logique d'edge vit en `private/`.

## 3. Deux paliers
- **PoC-now** : (a) **ranking** « venue la moins chère par modèle, maintenant » ; (b) **signal de
  timing** « loue maintenant vs attends » (le prix est-il bas vs son historique récent ?) ; (c)
  **backtest des économies** : sur l'historique, combien aurais-tu économisé en suivant le signal
  vs louer naïvement → métrique = **€ économisés / %**.
- **Institutional-target** : routing automatique multi-venues, alertes, contraintes (région/dispo).

## 4. Architecture
Logique pure dans `private/procurement/` : `cheapest.py` (ranking point-in-time), `timing.py`
(signal vs historique récent, **anti look-ahead**), `savings_backtest.py` (€ économisés). DI :
source de prix injectée (le cold store). Réutilise `core` en lecture.

## 5. Tests-first (aussi en privé)
Tests dans `private/procurement/tests/` ou `*.private.py` (gitignorés) : (a) ranking correct sur
fixture ; (b) **anti look-ahead** (décision à t sur données ≤ t — sinon le backtest d'économies est
faux) ; (c) le backtest d'économies = somme(coût naïf − coût routé) sur des prix connus.

## 6. Honnêteté (rule backtest-pitfalls)
Le « € économisé » est une **vraie** métrique (pas un PnL spéculatif) MAIS : (a) suppose que tu
loues vraiment ce volume ; (b) ignore coûts de migration entre venues ; (c) historique compute court
au début → économies estimées peu robustes. **Documente ces limites** dans une synthèse locale.

## 7. Reproductibilité (locale)
MLflow local OK (params + seed), mais **artefacts en local uniquement** (jamais poussés). La donnée
versionnée (cold store) rend le backtest rejouable.

## 8. Dépendances
- **Amont** : W1 (providers, dans `main`), P11 (storage), ≥2 venues réelles (Vast+RunPod suffisent
  pour démarrer ; s'améliore avec chaque venue W2 ajoutée).

## 9. Definition of Done (PoC-now, LOCAL)
- [ ] `private/procurement/` : ranking + timing + backtest d'économies, **anti look-ahead testé**.
- [ ] Tests verts (en local) ; synthèse locale (€ économisés estimés + limites honnêtes).
- [ ] **RIEN versionné/poussé** (vérifie `git status` : aucun fichier `private/` ni `*.private.*` suivi).
- [ ] Outil utilisable : « pour louer un H100 maintenant → venue X, ou attends ».
