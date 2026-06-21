# Crée un worktree partitionné pour travailler un module en parallèle.
# Usage : .\scripts\new-worktree.ps1 -Module ingestion
param(
    [Parameter(Mandatory=$true)][string]$Module
)
$branch = "feature/$Module"
$path   = "../lab-$Module"

git worktree add $path -b $branch
Write-Host ""
Write-Host "Worktree créé : $path  (branche $branch)" -ForegroundColor Green
Write-Host "Rappel : cette session ne doit écrire QUE dans le module '$Module'."
Write-Host "Voir docs/parallel-ops.md pour la partition de propriété."
Write-Host ""
Write-Host "Prochaine étape : ouvrir un terminal dans $path puis lancer 'claude'."
