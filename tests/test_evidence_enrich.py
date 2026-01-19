from datetime import datetime, timezone

from packages.core.schemas.chart import Observation, PatientChart, SourceRef
from packages.pipeline.evidence_enrich import enrich_evidence


def test_enrich_evidence_sets_file_path_and_timestamp() -> None:
    chart = PatientChart(
        patient_id="test",
        observations=[
            Observation(
                id="obs1",
                code="2160-0",
                code_system="http://loinc.org",
                effective_dt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        ],
    )
    risks = [
        {
            "rule_id": "lab_trend_creatinine",
            "severity": "medium",
            "message": "test",
            "evidence": [SourceRef(doc_id="Observation/obs1", resource_type="Observation", resource_id="obs1")],
        }
    ]
    enrich_evidence(risks, chart, "data/sample.json")
    evidence = risks[0]["evidence"][0]
    assert evidence.file_path == "data/sample.json"
    assert evidence.timestamp is not None
