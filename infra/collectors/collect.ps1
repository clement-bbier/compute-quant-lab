# Collecteur planifie - releve les prix GPU (Vast.ai + RunPod) et les accumule dans
# le cold store data/snapshots (CSV + Parquet). Concu pour Windows Task Scheduler.
#
# - Chemin du depot FIGE : le contexte Task Scheduler ne fournit pas $PSScriptRoot.
# - Le log est cree en premier et toute erreur est capturee -> on a toujours un diagnostic.
# - Charge .env (secrets) dans le process : jamais committe, jamais loggue.
# - Idempotent : relance, il n'ajoute aucun doublon (dedup par contenu de ligne).

$ErrorActionPreference = "Stop"
$repo = "C:\Users\cleme\Documents\04_Projets_Personnels\compute-quant-lab"
$log  = Join-Path $repo "infra\collectors\snapshot.log"

function Write-Log([string]$msg) {
    "$(Get-Date -Format o) $msg" | Out-File -FilePath $log -Append -Encoding UTF8
}

try {
    Set-Location $repo
    Write-Log "=== START collecte ==="

    $envFile = Join-Path $repo ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$') {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
            }
        }
    } else {
        Write-Log "WARN .env introuvable : $envFile"
    }

    $py = Join-Path $repo ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { throw "venv python introuvable : $py (lancer 'uv sync')" }

    $out = & $py -m infra.collectors.gpu_price_snapshot 2>&1 | Out-String
    Write-Log $out.Trim()
    Write-Log "=== END (exit $LASTEXITCODE) ==="
}
catch {
    Write-Log ("ERREUR : " + $_.Exception.Message)
    exit 1
}
