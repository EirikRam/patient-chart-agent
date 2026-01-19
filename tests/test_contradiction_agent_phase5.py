from pathlib import Path

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agents.contradiction_agent import run_contradiction_agent


def test_contradiction_agent_detects_conflict() -> None:
    sample_path = Path("tests/data/contradiction_bundle.json")
    resources = load_patient_dir(sample_path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    items = run_contradiction_agent(chart)
    assert len(items) == 1
    item = items[0]
    assert item.id
    assert item.severity
    assert item.message
    assert len(item.evidence) >= 2
    assert "should" not in item.message.lower()
    assert "recommend" not in item.message.lower()
