from datetime import date, datetime
from pathlib import Path

import pytest

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agents.timeline_agent import run_timeline_agent


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.combine(date.fromisoformat(value), datetime.min.time())


def test_timeline_agent_outputs_entries() -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    resources = load_patient_dir(sample_path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    entries = run_timeline_agent(chart, max_entries=10)
    assert isinstance(entries, list)
    assert len(entries) > 0

    parsed_dates = []
    for entry in entries:
        assert entry.date
        assert entry.type
        assert entry.summary
        assert entry.evidence
        assert entry.evidence[0].doc_id
        parsed_dates.append(_parse_iso(entry.date))

    for idx in range(len(parsed_dates) - 1):
        assert parsed_dates[idx] >= parsed_dates[idx + 1]
