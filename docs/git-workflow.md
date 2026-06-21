# Workflow Git parallèle du labo

> Comment plusieurs instances focalisées travaillent en parallèle sans casser
> `main`. Ce document décrit le **cycle de vie des branches et worktrees** ; la
> **propriété des modules** (qui écrit où) vit dans
> [parallel-ops.md](parallel-ops.md), source de vérité unique. Les deux se lisent
> ensemble : ici le « comment merger », là-bas le « qui possède quoi ».

## 1. Modèle de branches

| Branche | Rôle | Règles |
|---|---|---|
| `main` | Protégée, stable | Ne reçoit que des merges relus, CI verte. Jamais de commit direct, jamais de force-push. |
| `integration` | Convergence | Les features y mergent **d'abord**. C'est la base de toutes les branches de travail. |
| `feature/PNN-<nom>` | Une par projet/instance | Vit dans son propre worktree, branchée sur `integration`. |
| `chore/<sujet>` | Maintenance d'infra | Mêmes règles que `feature/*` (ex. cette mise en place d'orchestration). |

`PNN` = identifiant projet du roster (ex. `P01`, `P04`, `P08`). Une instance
focalisée = une branche `feature/PNN-<nom>` = un worktree = un module possédé.

## 2. Worktrees : 1 worktree = 1 module DISJOINT

Chaque instance travaille dans un worktree isolé, branché sur `integration` :

```bash
git worktree add ../lab-PNN -b feature/PNN-<nom> integration
```

Le worktree n'écrit **que** dans le module qu'il possède (cf. table de partition
de [parallel-ops.md](parallel-ops.md)). Pour lister / nettoyer :

```bash
git worktree list
git worktree remove ../lab-PNN      # une fois la feature mergée
```

## 3. Zone protégée

`CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` ne changent **que** via la
session de convergence (celle qui pilote `integration`), jamais dans un worktree
périphérique. Un worktree qui doit y toucher prépare un patch et le remonte à la
convergence. Sinon : conflits de merge garantis sur les fichiers les plus partagés.

## 4. Discipline anti-conflit (avant de merger une feature)

```bash
# Dans le worktree de la feature :
git fetch origin
git rebase origin/integration       # rejoue la feature sur la base à jour
# relancer les tests : pytest && ruff check . && mypy core
git switch integration
git merge --no-ff feature/PNN-<nom>  # ou via PR
```

- **Rebase avant merge** : la feature se rejoue proprement sur `integration` à jour.
- **Tests verts obligatoires** après rebase, avant merge.
- **`--no-ff`** (ou PR) : on garde une trace explicite du point de merge.

## 5. integration → main

`integration` ne remonte vers `main` que lorsque la **CI est verte** et la **revue
faite**. Le merge se fait en **fast-forward propre** (pas de divergence) :

```bash
git switch main
git merge --ff-only integration
```

## 6. Interdits

- ❌ Jamais de commit direct sur `main`.
- ❌ Jamais de force-push sur `main` ou `integration`.
- ❌ Jamais d'écriture hors de son module possédé depuis un worktree.
- ⚠️ Tout push sur une branche partagée (`integration`, `main`) se fait après
  confirmation explicite du directeur de recherche.

## 7. Cycle type d'une instance

1. La convergence crée/maintient `integration` à jour avec `main`.
2. L'instance ouvre son worktree : `git worktree add ../lab-PNN -b feature/PNN-<nom> integration`.
3. Elle travaille **uniquement dans son module**, commits sémantiques.
4. Avant merge : `git fetch && git rebase origin/integration`, tests verts.
5. La convergence merge `feature/PNN-<nom>` → `integration` (PR ou `--no-ff`).
6. Quand un palier est atteint et la CI verte : `integration` → `main` en `--ff-only`.
