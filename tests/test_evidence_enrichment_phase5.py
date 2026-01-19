import json
from pathlib import Path

import pytest

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agent_pipeline import run_agent_pipeline
from packages.pipeline.evidence_enrich import enrich_result_evidence


def _dump_json(result) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    return result.json()


def _collect_timestamps(payload: dict) -> list:
    timestamps = []
    for risk in payload.get("risks", []) or []:
        for evidence in risk.get("evidence", []) or []:
            if evidence.get("timestamp") is not None:
                timestamps.append(evidence.get("timestamp"))
    for entry in payload.get("timeline", []) or []:
        for evidence in entry.get("evidence", []) or []:
            if evidence.get("timestamp") is not None:
                timestamps.append(evidence.get("timestamp"))
    return timestamps


def test_evidence_enrichment_phase5() -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    resources = load_patient_dir(sample_path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    result = run_agent_pipeline(sample_path, enable_agents=True, mode="mock")
    enrich_result_evidence(result, chart, str(sample_path))

    payload = json.loads(_dump_json(result))
    file_path_values = []
    for risk in payload.get("risks", []) or []:
        for evidence in risk.get("evidence", []) or []:
            if evidence.get("file_path"):
                file_path_values.append(evidence.get("file_path"))
    for entry in payload.get("timeline", []) or []:
        for evidence in entry.get("evidence", []) or []:
            if evidence.get("file_path"):
                file_path_values.append(evidence.get("file_path"))
    assert file_path_values
    assert str(sample_path) in file_path_values

    for ts in _collect_timestamps(payload):
        assert isinstance(ts, str)

    result_disabled = run_agent_pipeline(sample_path, enable_agents=False, mode="mock")
    enrich_result_evidence(result_disabled, chart, str(sample_path))
    assert result_disabled.timeline is None
    assert result_disabled.missing_info is None
    assert result_disabled.contradictions is None
