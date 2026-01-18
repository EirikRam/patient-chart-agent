from datetime import datetime

from packages.core.schemas.chart import Observation, PatientChart, SourceRef
from packages.risklib.rules import discover_rules


def test_discover_rules_returns_expected_runners() -> None:
    runners = discover_rules()
    expected = {
        "duplicate_therapy",
        "followup_missing",
        "lab_a1c_elevated",
        "lab_trend_creatinine",
        "lab_trend_potassium",
        "med_allergy_conflict",
        "vitals_bp_elevated",
        "vitals_bmi_obesity",
    }
    assert expected == set(runners.keys())


def test_rule_runners_return_list() -> None:
    runners = discover_rules()
    chart = PatientChart(patient_id="test")
    for runner in runners.values():
        result = runner(chart)
        assert isinstance(result, list)


def test_lab_a1c_elevated_hits() -> None:
    runners = discover_rules()
    chart = PatientChart(
        patient_id="test",
        observations=[
            Observation(
                id="a1c",
                code="4548-4",
                code_system="http://loinc.org",
                value=7.2,
                effective_dt=datetime(2024, 1, 1),
                sources=[SourceRef(doc_id="Observation/a1c")],
            )
        ],
    )
    result = runners["lab_a1c_elevated"](chart)
    assert result


def test_vitals_bp_elevated_hits() -> None:
    runners = discover_rules()
    chart = PatientChart(
        patient_id="test",
        observations=[
            Observation(
                id="bp",
                code="85354-9",
                code_system="http://loinc.org",
                effective_dt=datetime(2024, 1, 1),
                components=[
                    {
                        "code": "8480-6",
                        "code_system": "http://loinc.org",
                        "value": 150,
                        "unit": "mm[Hg]",
                    },
                    {
                        "code": "8462-4",
                        "code_system": "http://loinc.org",
                        "value": 95,
                        "unit": "mm[Hg]",
                    },
                ],
                sources=[SourceRef(doc_id="Observation/bp")],
            )
        ],
    )
    result = runners["vitals_bp_elevated"](chart)
    assert result


def test_vitals_bmi_obesity_hits() -> None:
    runners = discover_rules()
    chart = PatientChart(
        patient_id="test",
        observations=[
            Observation(
                id="bmi",
                code="39156-5",
                code_system="http://loinc.org",
                value=32.0,
                effective_dt=datetime(2024, 1, 1),
                sources=[SourceRef(doc_id="Observation/bmi")],
            )
        ],
    )
    result = runners["vitals_bmi_obesity"](chart)
    assert result
