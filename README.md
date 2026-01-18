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
