#!/usr/bin/env bash
# Crée un worktree partitionné. Usage : ./scripts/new-worktree.sh ingestion
set -euo pipefail
module="${1:?Usage: ./scripts/new-worktree.sh <module>}"
branch="feature/${module}"
path="../lab-${module}"
git worktree add "$path" -b "$branch"
echo ""
echo "Worktree créé : $path (branche $branch)"
echo "Rappel : cette session ne doit écrire QUE dans le module '$module'."
echo "Voir docs/parallel-ops.md pour la partition de propriété."
