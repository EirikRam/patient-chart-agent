param(
    [string]$SamplePath = "data\raw\fhir_ehr_synthea\samples_100\Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
Set-Location $repoRoot

$venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
}

$sampleFullPath = Join-Path $repoRoot $SamplePath
if (-not (Test-Path $sampleFullPath)) {
    Write-Host "Sample file not found: $sampleFullPath"
    Write-Host "Run with -SamplePath pointing to an existing patient bundle."
    exit 1
}

$apiProcess = Start-Process -FilePath "uvicorn" -ArgumentList "apps.api.main:app --port 8000" -PassThru -NoNewWindow

$healthUrl = "http://127.0.0.1:8000/healthz"
$maxAttempts = 30
$ready = $false
for ($i = 0; $i -lt $maxAttempts; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
        if ($resp.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Host "API did not become ready at $healthUrl"
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force
    }
    exit 1
}

python -m apps.client.analyze_client --url http://127.0.0.1:8000 --path $SamplePath --mode mock

if ($env:OPENAI_API_KEY) {
    python -m apps.client.analyze_client --url http://127.0.0.1:8000 --path $SamplePath --mode llm
} else {
    Write-Host "OPENAI_API_KEY not set; skipping llm mode."
}

if ($apiProcess -and -not $apiProcess.HasExited) {
    Stop-Process -Id $apiProcess.Id -Force
}
