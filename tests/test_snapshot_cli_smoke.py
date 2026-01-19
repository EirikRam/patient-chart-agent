from pathlib import Path

import pytest

from packages.pipeline.steps.snapshot import build_snapshot


def test_build_snapshot_from_sample_file() -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")
    snapshot = build_snapshot(str(sample_path))
    assert snapshot.startswith("Patient:")
