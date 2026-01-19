from pathlib import Path

import pytest

from apps.client.analyze_client import REPO_ROOT


def test_relative_path_resolution() -> None:
    sample_rel = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    resolved = (REPO_ROOT / sample_rel).resolve()
    if not resolved.exists():
        pytest.skip("sample data not available")
    assert resolved.is_file()
