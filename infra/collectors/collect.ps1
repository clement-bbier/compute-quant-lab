# Collecteur planifie - releve les prix GPU (Vast.ai + RunPod) dans data/snapshots
# (CSV + Parquet). Concu pour Windows Task Scheduler. Idempotent.
#
# Note : le collecteur Python logge sur stderr (comportement normal de logging).
# On ne traite donc PAS stderr comme une erreur (EAP=Continue) ; succes/echec reel
# = code de sortie Python (0 = OK), reporte au Planificateur via 'exit $code'.

$ErrorActionPreference = "Continue"
$repo = "C:\Users\cleme\Documents\04_Projets_Personnels\compute-quant-lab"
$log  = Join-Path $repo "infra\collectors\snapshot.log"

function Write-Log([string]$msg) {
    "$(Get-Date -Format o) $msg" | Out-File -FilePath $log -Append -Encoding UTF8
}

Set-Location $repo
Write-Log "=== START collecte ==="

# Charge .env (secrets) dans le process : VASTAI_API_KEY / RUNPOD_API_KEY / ...
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
if (-not (Test-Path $py)) {
    Write-Log "ERREUR : venv python introuvable : $py (lancer 'uv sync')"
    exit 1
}

$out  = & $py -m infra.collectors.gpu_price_snapshot 2>&1 | Out-String
$code = $LASTEXITCODE
Write-Log $out.Trim()
Write-Log "=== END (exit $code) ==="
exit $code
