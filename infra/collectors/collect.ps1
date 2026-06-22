# Collecteur planifié — relève les prix GPU (Vast.ai + RunPod) et les accumule dans
# le cold store (data/snapshots : CSV + Parquet). Conçu pour Windows Task Scheduler.
#
# Charge .env (secrets) dans l'environnement du process — jamais committé, jamais loggué.
# Idempotent : relancé, il n'ajoute aucun doublon (dédup par contenu de ligne).

$ErrorActionPreference = "Continue"

# Racine du dépôt = deux niveaux au-dessus de ce script (infra/collectors/).
$repo = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $repo

# Charge les variables de .env dans le process (VASTAI_API_KEY / RUNPOD_API_KEY / …).
$envFile = Join-Path $repo ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

$log = Join-Path $repo "infra\collectors\snapshot.log"
"=== $(Get-Date -Format o) — collecte ===" | Add-Content $log
& "$repo\.venv\Scripts\python.exe" -m infra.collectors.gpu_price_snapshot *>> $log
