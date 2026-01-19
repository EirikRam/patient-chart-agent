from datetime import datetime, timedelta
from pathlib import Path

import pytest

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agents.missing_info_agent import run_missing_info_agent

LOINC_SYSTEM = "http://loinc.org"
A1C_CODES = {"4548-4"}
BP_PANEL_CODE = "85354-9"


def _obs_date(obs) -> datetime | None:
    return obs.effective_dt or obs.effective


def _reference_date(chart) -> datetime | None:
    dates = []
    for obs in chart.observations:
        date_value = _obs_date(obs)
        if date_value:
            dates.append(date_value)
    for encounter in chart.encounters:
        date_value = encounter.start or encounter.end
        if date_value:
            dates.append(date_value)
    return max(dates) if dates else None


def _has_condition(chart, tokens: tuple[str, ...]) -> bool:
    for condition in chart.conditions:
        text = " ".join([condition.display or "", condition.code or ""]).lower()
        if any(token in text for token in tokens):
            return True
    return False


def _recent_a1c(chart, reference_date: datetime) -> bool:
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code not in A1C_CODES:
            continue
        date_value = _obs_date(obs)
        if date_value and date_value >= reference_date - timedelta(days=365):
            return True
    return False


def test_missing_info_agent_outputs_entries() -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    resources = load_patient_dir(sample_path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    items = run_missing_info_agent(chart)
    assert isinstance(items, list)
    for item in items:
        assert item.id
        assert item.severity
        assert item.message
        assert "should" not in item.message.lower()
        assert "recommend" not in item.message.lower()

    reference_date = _reference_date(chart)
    if reference_date:
        diabetes_present = _has_condition(chart, ("diabetes",))
        if diabetes_present and not _recent_a1c(chart, reference_date):
            ids = {item.id for item in items}
            assert "missing_hba1c_recent" in ids
