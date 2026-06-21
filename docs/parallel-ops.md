# Opérations parallèles — le modèle « usine de recherche »

Comment faire tourner beaucoup d'agents, de worktrees et de terminaux en parallèle
sans que ça s'effondre en conflits de merge.

## Les trois voies

| Voie | Mécanisme | Parallélisme | Sortie |
|---|---|---|---|
| **Collecte** | essaim de subagents (`/market-scan`) | élevé (≈10) | synthèses → `references/` |
| **Construction** | git worktrees + sessions | modéré | code → branche d'intégration |
| **Convergence** | 1 session pilote | séquentiel | review, merge, MAJ `CLAUDE.md` |

Collecte : « beaucoup d'agents » est sans risque, ils ne renvoient que des synthèses.
Construction : le risque est git, pas Claude → règle de partition ci-dessous.
Convergence : le vrai goulot est humain → cadence de réconciliation.

## Règle d'or des worktrees : 1 worktree = 1 module DISJOINT

Chaque session parallèle ne possède qu'un dossier et n'écrit que dedans.
Partition de propriété (évite les collisions de merge) :

| Worktree / branche | Possède (écrit uniquement ici) |
|---|---|
| `feature/ingestion` | `core/ingestion/`, `infra/mcp-servers/`, `infra/collectors/` |
| `feature/data-quality` | `core/data_quality/` |
| `feature/features` | `core/features/` |
| `feature/models` | `core/models/` |
| `feature/backtest` | `core/backtest/` |
| `feature/dashboard` | `projects/01_digital_spark_spread/` |
| `feature/research` | `references/` |

### Zone protégée (NE PAS modifier dans un worktree périphérique)
`CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` changent rarement et passent
UNIQUEMENT par la session de convergence. Sinon, conflits garantis.

## Garde-fous hérités automatiquement
Les hooks et rules vivent dans `.claude/` committé : chaque worktree et chaque session
hérite du blocage d'écriture sur `data/raw/`, du formatage auto et des règles anti-look-ahead.
Tu peux paralléliser sans craindre pour l'intégrité des données.

## Cadence suggérée
1. Lancer un `/market-scan` (voie collecte) → alimente `references/`.
2. Ouvrir 2-4 worktrees sur des modules disjoints (voie construction).
3. Une fois par cycle, la session pilote merge les branches dans `integration`,
   relance les tests, met à jour l'index `CLAUDE.md`, réconcilie les synthèses.

## Surveiller les sessions
`claude agents` ouvre la vue des sessions (en cours / bloquées / terminées),
utile quand beaucoup de terminaux tournent.
