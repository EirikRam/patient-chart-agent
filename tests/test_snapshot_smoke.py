from datetime import datetime

from packages.pipeline.steps.snapshot import build_snapshot_from_chart
from packages.core.schemas.chart import Observation, PatientChart, SourceRef


def test_snapshot_includes_bmi_and_a1c() -> None:
    chart = PatientChart(
        patient_id="test",
        demographics={"gender": "female", "birth_date": "1980-01-01"},
        observations=[
            Observation(
                id="bmi",
                code="39156-5",
                code_system="http://loinc.org",
                value=32.0,
                unit="kg/m2",
                effective_dt=datetime(2024, 1, 1),
                sources=[SourceRef(doc_id="Observation/bmi")],
            ),
            Observation(
                id="a1c",
                code="4548-4",
                code_system="http://loinc.org",
                value=6.1,
                unit="%",
                effective_dt=datetime(2024, 2, 1),
                sources=[SourceRef(doc_id="Observation/a1c")],
            ),
        ],
    )
    snapshot = build_snapshot_from_chart(chart)
    assert "BMI (39156-5)" in snapshot
    assert "A1c (4548-4)" in snapshot
