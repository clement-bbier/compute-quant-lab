# Creates a partitioned worktree to work on a module in parallel.
# Usage: .\scripts\new-worktree.ps1 -Module ingestion
param(
    [Parameter(Mandatory=$true)][string]$Module
)
$branch = "feature/$Module"
$path   = "../lab-$Module"

# Lab standard (docs/git-workflow.md §2): branch off `integration`, not
# whatever ref HEAD happens to be pointing at.
git worktree add $path -b $branch integration
Write-Host ""
Write-Host "Worktree created: $path  (branch $branch)" -ForegroundColor Green
Write-Host "Reminder: this session must write ONLY into the '$Module' module."
Write-Host "See docs/parallel-ops.md for the ownership partition."
Write-Host ""
Write-Host "Next step: open a terminal in $path then run 'claude'."
