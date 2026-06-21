<!--
TEMPLATE d'instance focalisée. Copier dans instances/PNN_<nom>.md et remplir.
Tout texte entre <…> est un placeholder. Le fichier rempli doit être
AUTO-SUFFISANT : exécutable en MODE PLAN dans une session vierge, sans contexte
externe autre que le dépôt lui-même.
-->

# PNN — <Nom du projet>

> **À l'instance qui reçoit ce fichier :** tu démarres en **MODE PLAN**. Ne code
> rien tant que le plan n'est pas validé. Lis le `CLAUDE.md` racine, ce fichier,
> `docs/git-workflow.md`, `docs/parallel-ops.md` et le module que tu possèdes.
> Ton livrable de session = un plan d'implémentation, pas du code.

## 0. Identité & cadre Git
- **ID projet** : PNN
- **Branche** : `feature/PNN-<nom>`
- **Worktree** : `git worktree add ../lab-PNN -b feature/PNN-<nom> integration`
- **Module possédé (écris UNIQUEMENT ici)** : `<core/xxx/ + projects/NN_nom/>`
- **Zone protégée (NE PAS toucher ici)** : `CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` → patch remonté à la convergence.

## 1. Thèse
<Le pari de recherche en 3-5 lignes : quel signal/edge, pourquoi il existe, comment il se monétise sur un desk.>

## 2. Flux de données vérifiés
<Pour chaque source : unité, fuseau (UTC), fréquence, accès, statut. Distinguer
le RÉEL (ENTSO-E/PJM, spot Silicon Data) du SIMULÉ (courbe forward CME non listée).
Tout I/O passe par core/ ; jamais de chemin en dur.>

| Source | Réel/Simulé | Unité | Fréquence | Accès |
|---|---|---|---|---|
| <…> | <…> | <…> | <…> | <…> |

## 3. Deux paliers
### 3a. PoC-now (preuve exécutable, qualité desk)
<Le périmètre minimal qui prouve l'edge de bout en bout, reproductible. Ce qu'on
livre cette fois-ci. Polyglotte autorisé dès maintenant sur les jambes critiques.>
### 3b. Institutional-target (cible desk réel)
<Ce que deviendrait la brique en production desk : latence, robustesse, échelle,
temps réel, langages bas niveau. Documenté, pas codé maintenant.>

## 4. Architecture (SOLID / DI)
<Interfaces et inversions de dépendance. Quelles abstractions (Protocol/ABC),
quelles implémentations injectées, points d'extension. Pourquoi c'est testable et
substituable (ex. source de prix mockable, moteur de coût injecté).>

## 5. Code à faire grossir
- **Dans `core/`** : <briques réutilisables qui remontent en fondation.>
- **Dans `projects/NN_nom/`** : <le spécifique au projet (notebooks, dashboard, src).>
- **Polyglotte** : <jambe(s) en Rust/C#/C++ si latence/perf le justifie, sinon « aucune ».>

## 6. Tests-first
<Les tests écrits AVANT le code : cas nominaux, anti look-ahead, contrats
d'interface, propriété point-in-time. pytest. Critère de « vert » avant merge.>

## 7. Reproductibilité
<DVC pour la donnée (version), MLflow pour params+métriques+artefacts, SHA git.
Comment un tiers rejoue exactement le résultat.>

## 8. CROISSANCE DU LABO (obligatoire)
> Tout projet doit nourrir la fondation. Renseigner explicitement, même si « aucun ».
- **Nouveaux employés** (via `agent-architect` + skill `new-agent`, jamais à la main) : <agents/skills/rules/hooks à fabriquer pour ce projet.>
- **Références** (couche savoir → `references/`) : <papiers, méthodo à distiller.>
- **Sources / MCP** : <nouvelles sources de données ou serveurs MCP à brancher.>
- **Skills / rules** : <playbooks ou contraintes path-scopées à ajouter.>

## 9. Dépendances
- **Amont (projets)** : <PNN dont celui-ci dépend ; attendre leur merge.>
- **Modules core requis** : <core/… consommés en lecture.>
- **Externe** : <libs, tokens, accès.>

## 10. Risques & angles morts
<Look-ahead, overfitting, data snooping, survivorship, fragilité d'une source,
confusion réel/simulé. Pour chaque risque : comment le plan le neutralise.
Le risk-validator (agent adversaire) doit pouvoir s'y attaquer.>

## 11. Definition of Done (PoC-now)
<Liste cochable : tests verts, ruff/mypy verts, run MLflow loggué, données DVC,
synthèse écrite, rien hors du module possédé, prêt à merger vers integration.>
