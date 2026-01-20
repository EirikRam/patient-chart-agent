# patient-chart-agent

Agentic system for summarizing patient charts from synthetic EHR/FHIR data.  
Ingests clinical notes, labs, medications, and vitals to produce clinician-style summaries, event timelines, risk flags, and missing-information checks with source-level citations. Designed for faithfulness, auditability, and safe clinical decision support.

---

## Overview

**patient-chart-agent** is a multi-agent clinical intelligence system that analyzes structured electronic health record (EHR) data and produces a faithful, traceable, clinician-style chart review.

The system is designed to answer a practical clinical question:

> *“Given this patient chart, what matters right now, what looks risky, what is missing or contradictory, and where is the evidence?”*

Rather than acting as a conversational chatbot, the system operates as a **deterministic analysis pipeline** with optional LLM assistance, prioritizing:
- Evidence traceability
- Auditability
- Safety
- Readability for clinical workflows

All examples use **synthetic patient data** generated via Synthea.

---

## Why This Exists

Modern patient charts are fragmented, verbose, and internally inconsistent. Clinicians, care managers, and clinical reviewers often must manually scan:
- Long medication lists
- Repeated or conflicting problem entries
- Disconnected lab and vital trends
- Notes that reference findings without clear supporting data

This system is designed to **reduce cognitive load** by:
- Structuring key clinical information
- Highlighting potential risks and data gaps
- Preserving direct links to source evidence

It does **not** diagnose conditions or recommend treatments.

---

## Core Capabilities

The system produces a single consolidated analysis containing:

- **Patient Snapshot**
  - Demographics
  - Active problems
  - Medications
  - Key vitals and laboratory values

- **Clinical Risk Flags**
  - Rule-based safety and trend checks
  - Severity classification (low / medium / high)
  - Plain-language rationale
  - Source-level evidence

- **Event Timeline**
  - Extracted and ordered clinical events when available
  - Explicit empty-state handling when data is insufficient

- **Missing Information & Contradictions**
  - Gaps in documentation
  - Conflicting entries across the chart
  - Unresolved references (e.g., mentioned labs without values)

- **LLM-Assisted Narrative (Optional)**
  - Clinician-style summary
  - Strictly constrained to verified snapshot data
  - Automatically disabled or flagged if generation fails

- **Citations**
  - Every claim links back to its originating FHIR resource
  - File paths and timestamps preserved for auditability

---

## Agentic Architecture

This project is intentionally designed as a **multi-agent system**, with each agent responsible for a narrow, well-defined task.

### Implemented Agents

- **Ingestion & Normalization Agent**
  - Parses FHIR bundles
  - Normalizes labs, vitals, medications, and problems into a canonical schema
  - Assigns stable identifiers for citation

- **Snapshot Agent**
  - Produces a concise, problem-oriented patient overview
  - Acts as the single source of truth for downstream agents

- **Risk Flagging Agent**
  - Applies deterministic clinical safety and trend rules
  - Flags potential issues such as:
    - Abnormal lab trends
    - Obesity-range BMI
    - Elevated blood pressure
    - Prediabetes-range A1c
  - Attaches explicit evidence for every flag

- **Missing Information / Contradiction Agent**
  - Identifies inconsistencies across notes, labs, and problem lists
  - Surfaces documentation gaps that may affect clinical interpretation

- **Verification Agent**
  - Ensures every output statement is supported by evidence
  - Removes or suppresses uncited claims

- **Narrative Agent (Optional, LLM-Assisted)**
  - Generates a clinician-style narrative summary
  - Operates **only** on verified snapshot text
  - Enforces strict JSON and citation discipline
  - Automatically falls back to deterministic output on failure

This separation allows the system to remain explainable, testable, and extensible.

---

## Retrieval-Augmented Generation (RAG)

When LLM mode is enabled, the system uses a **RAG-based approach**:

- **Patient Data Retrieval**
  - Structured snapshot content
  - Normalized lab and vital series
  - Curated note excerpts

- **Clinical Knowledge Retrieval**
  - Rule explanations
  - Safety heuristics
  - Trend interpretation logic

The LLM is **not permitted** to invent clinical facts.  
It may only synthesize narratives from retrieved, verified inputs.

---

## End-to-End Workflow

1. Load synthetic FHIR bundle
2. Normalize patient data into a canonical chart
3. Generate a deterministic patient snapshot
4. Apply risk rules and contradiction checks
5. Enrich findings with evidence metadata
6. (Optional) Generate constrained narrative summary
7. Render results as structured JSON or human-readable Markdown

---

## Demo: Patient Chart Analysis Report

The following is an example report generated from a synthetic EHR bundle.

### Sample Output (LLM Mode)

![Patient Analysis Report Demo](docs/images/report_demo.png)
<img width="807" height="847" alt="LLM Sample Screenshot" src="https://github.com/user-attachments/assets/2e93acb1-e9bb-48dd-b0fb-1813b1574da1" />


**Excerpt:**
> Female, age 28, with obesity-range BMI (32.21) and elevated blood pressure (122/92).  
> Hemoglobin A1c of 5.96% falls within the prediabetes range.  
> Findings are derived from structured vitals and laboratory observations and are fully traceable to source records.

Full reports:
- 📄 [`Berna338_llm.md`](artifacts/reports/Berna338_llm.md) — LLM-assisted mode
- 📄 [`Berna338.md`](artifacts/reports/Berna338.md) — deterministic mock mode

---

## System Architecture Diagram

> **Architecture / Agent Wiring Diagram (Coming Next)**  
>  
> A professional system diagram will be added to illustrate:
> - Agent boundaries
> - Data flow between ingestion, analysis, and verification
> - RAG retrieval paths
> - CLI and API entry points

---

## Intended Users & Applications

This system is intended for:

- Clinical informatics teams
- Care management and chart review workflows
- Clinical decision support prototyping
- AI safety and auditability research
- Healthcare data engineering and ML portfolios

Potential applications include:
- Pre-visit chart review
- Clinical quality and safety checks
- Documentation consistency auditing
- Synthetic data analysis pipelines

---

## Safety, Scope, and Limitations

- Uses **synthetic patient data only**
- Provides **informational analysis**, not diagnosis
- Does **not** recommend treatments or clinical actions
- Enforces citation-first output discipline
- Designed to fail safely when information is insufficient

---

## Quick Start

```bash
# Deterministic analysis (no API key required)
python apps/worker/run_analyze.py data/raw/fhir_ehr_synthea/samples_100 \
  --mode mock --format md --out artifacts/reports/sample.md

# LLM-assisted analysis (optional)
python apps/worker/run_analyze.py data/raw/fhir_ehr_synthea/samples_100 \
  --mode llm --format md --out artifacts/reports/sample_llm.md


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
