---
name: new-agent
description: Protocole de fabrication d'un mécanisme d'orchestration (subagent, skill, rule ou hook) via le méta-agent agent-architect. À invoquer pour créer ou réviser un employé du labo. Trigger : /new-agent.
---
# New Agent — protocole de fabrication

> Aucun agent/skill/rule/hook ne se crée à la main. Cette procédure est exécutée
> par (ou pour) l'agent `agent-architect`. Elle est idempotente : relancée, elle
> ne casse rien et propose un diff plutôt qu'un écrasement.

## 1. Cadrer la responsabilité unique
Formuler la mission en une phrase. Si la phrase contient « et » sur deux missions
distinctes → **scinder** en deux mécanismes. Un fourre-tout est un refus.

## 2. Choisir le mécanisme
| Besoin | Mécanisme | Emplacement |
|---|---|---|
| Un rôle qui travaille en isolation et renvoie une synthèse | **subagent** | `.claude/agents/X.md` |
| Une méthode/playbook réutilisable invoquée à la demande | **skill** | `.claude/skills/X/SKILL.md` |
| Une invariante path-scopée toujours appliquée | **rule** | `.claude/rules/X.md` |
| Un garde-fou déterministe qui DOIT se déclencher | **hook** | `.claude/settings.json` |

Tranchage : « à coup sûr » → hook ; « invariante sur des fichiers » → rule ;
« méthode réutilisable » → skill ; « travailleur délégué » → subagent.

## 3. Appliquer le moindre privilège (subagents)
Lister le strict minimum d'outils. Lecture/recherche seule → `Read, Grep, Glob`.
Ajouter `Write/Edit` seulement s'il produit des fichiers, `Bash` seulement s'il
exécute. Justifier chaque outil. Choisir `model` : `sonnet` par défaut, `opus`
si conception/jugement élevé.

## 4. Respecter le contrat de frontmatter
- **Agent** : `name`, `description` (finit par « À appeler pour… »), `tools`, `model` ;
  corps « Tu es… » concis en français, clôture « Tu renvoies une synthèse : … ».
- **Skill** : `name`, `description` (déclencheur explicite) ; corps en étapes numérotées.

## 5. Vérifier l'idempotence avant d'écrire
Le fichier existe-t-il déjà ? S'il diffère, **montrer un diff et demander** avant
toute modification. Sinon, créer.

## 6. Tester la découverte
Confirmer que le mécanisme est bien repéré (l'agent/skill apparaît dans la liste,
le hook se déclenche sur un cas factice, la rule matche le bon path). Pas de test
vert → pas de livraison.

## 7. Enregistrer (zone protégée → convergence)
Préparer le patch : ligne au §6 roster de `CLAUDE.md` racine, et si un nouveau
module possédé apparaît, ligne dans la table de partition de `docs/parallel-ops.md`.
Ces fichiers de la **zone protégée** ne changent QUE via la session de convergence :
on prépare le patch, on ne l'applique pas depuis un worktree périphérique.

## 8. Synthèse
Renvoyer : mécanisme + justification, outils + justification, fichiers touchés,
résultat du test, patch d'enregistrement à appliquer, risques.
