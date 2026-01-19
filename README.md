## Local Setup (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
python apps/worker/sanity_check.py
```

Create a `.env` from `.env.example` and set:
`SYNTHEA_100_DIR=data/raw/fhir_ehr_synthea/samples_100`
`SYNTHEA_1000_DIR=data/raw/fhir_ehr_synthea/samples_1000`

## API

Run the API:

```powershell
uvicorn apps.api.main:app --reload --port 8000
```

Run API (Windows):

```powershell
.\scripts\dev.ps1
```

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

Analyze (mock + llm):

```powershell
$payload = @{ path = "data\raw\fhir_ehr_synthea\samples_100\Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"; mode = "mock" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/analyze -ContentType "application/json" -Body $payload

$payload = @{ path = "data\raw\fhir_ehr_synthea\samples_100\Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"; mode = "llm" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/analyze -ContentType "application/json" -Body $payload
```

Client usage:

```powershell
python apps/client/analyze_client.py --url http://127.0.0.1:8000 --path data\raw\fhir_ehr_synthea\samples_100\Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json --mode mock
python apps/client/analyze_client.py --url http://127.0.0.1:8000 --path data\raw\fhir_ehr_synthea\samples_100\Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json --mode llm
python apps/client/analyze_client.py --url http://127.0.0.1:8000 --path data\raw\fhir_ehr_synthea\samples_100\Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json --mode mock --pretty
```

LLM mode requires `OPENAI_API_KEY`.

## Test API

```powershell
python -m pytest -q
```

## Quality Gate

Deterministic pre-commit checks:

```powershell
python scripts/quality_gate.py
```

## CI

CI runs the same quality gate command:

```powershell
python scripts/quality_gate.py
```

Local CI parity (install dev/test deps):

```powershell
python -m pip install -e ".[dev]"
```

## Quick Demo (Windows)

```powershell
.\scripts\demo.ps1
```

This starts the API, waits for `/healthz`, runs the client in mock mode, and runs llm mode if `OPENAI_API_KEY` is set.
