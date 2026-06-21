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

## 8. Worktrees — pratiques natives Claude Code

> Distillé de la doc officielle « Run parallel sessions with worktrees » et des
> retours d'usage 2026 (liens en §9). La méthode manuelle de la §2 reste le
> **standard du labo** (base = `integration`, nommage `feature/PNN-<nom>`) ; ce qui
> suit l'outille et la rend ergonomique.

### Deux façons de créer un worktree

- **Manuelle (standard labo)** — base et nom explicites, branchée sur `integration`,
  puis on **initialise l'environnement dans chaque worktree** (checkout neuf) :

  ```bash
  git worktree add ../lab-PNN -b feature/PNN-<nom> integration
  cd ../lab-PNN && uv sync --extra dev
  ```

- **Native Claude Code (ad hoc / analyse)** — `claude --worktree <nom>` crée un
  worktree sous `.claude/worktrees/<nom>/`. ⚠️ Il branche depuis `origin/HEAD`
  (= `main`), **pas** `integration` : à réserver aux sessions jetables (lecture de
  logs, requêtes). Pour partir de l'état local, régler `worktree.baseRef: "head"`
  dans les settings.

### Propagation des secrets (`.worktreeinclude`)

Un worktree est un checkout neuf : `.env` (gitignoré) n'y est **pas**. Le fichier
`.worktreeinclude` (syntaxe `.gitignore`) liste les fichiers gitignorés à recopier
automatiquement dans chaque nouveau worktree. **Indispensable ici** : les connecteurs
(ENTSO-E, Silicon Data) ont besoin des tokens. Voir [`.worktreeinclude`](../.worktreeinclude).

### Subagents en worktree isolé

Un employé du labo peut tourner dans son propre worktree en ajoutant
`isolation: worktree` à son frontmatter (ou « utilise un worktree pour tes agents »).
Idéal pour les gros lots disjoints : chaque agent teste de bout en bout puis ouvre une PR.

### Baseline de tests propre (pratique-clé)

Avant de confier un worktree à une instance : le créer, lancer `pytest && ruff check .
&& mypy core` **immédiatement**, confirmer le vert. Après le travail de l'instance,
relancer la même suite : toute nouvelle erreur devient ainsi **imputable** à
l'instance, pas à un état préexistant.

### Orientation quand beaucoup de sessions tournent

Nommer les worktrees, alias shell pour sauter de l'un à l'autre, onglets de terminal
colorés, notifications activées, et garder un worktree « analyse » dédié aux logs /
requêtes. Le roster et les prompts d'instances (`docs/orchestration/`) jouent le rôle
de **document de tâches partagé** : chaque instance lit son module possédé et n'écrit
que dedans (anti-collision, cf. partition de [parallel-ops.md](parallel-ops.md)).

### Nettoyage

`git worktree list` pour l'inventaire ; `git worktree remove ../lab-PNN` une fois la
feature mergée (`--force` si modifs non committées). Les worktrees natifs sans
changement sont balayés automatiquement après `cleanupPeriodDays`.

## 9. Sources

- Claude Code — *Run parallel sessions with worktrees* : <https://code.claude.com/docs/en/worktrees>
- Claude Code — *Power user tips* : <https://support.claude.com/en/articles/14554000-claude-code-power-user-tips>
