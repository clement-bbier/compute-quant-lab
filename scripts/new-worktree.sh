#!/usr/bin/env bash
# Creates a partitioned worktree. Usage: ./scripts/new-worktree.sh ingestion
set -euo pipefail
module="${1:?Usage: ./scripts/new-worktree.sh <module>}"
branch="feature/${module}"
path="../lab-${module}"
git worktree add "$path" -b "$branch"
echo ""
echo "Worktree created: $path (branch $branch)"
echo "Reminder: this session must write ONLY into the '$module' module."
echo "See docs/parallel-ops.md for the ownership partition."
