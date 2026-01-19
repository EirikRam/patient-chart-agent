param(
    [int]$Port = 8000
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
Set-Location $repoRoot

$venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
}

uvicorn apps.api.main:app --reload --port $Port
