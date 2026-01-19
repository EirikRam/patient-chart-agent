import json
from pathlib import Path

import pytest

from tests.golden.utils import compare_json, generate_result_json, normalize_result


GOLDEN_CASES = [
    (
        Path(
            "data/raw/fhir_ehr_synthea/samples_100/"
            "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
        ),
        Path("tests/golden/Berna338_Moore224_phase5_mock_agents.json"),
    ),
    (
        Path(
            "data/raw/fhir_ehr_synthea/samples_100/"
            "Kris249_Moore224_45dff467-def6-2132-a03a-5950e203b5c8.json"
        ),
        Path("tests/golden/Kris249_Moore224_phase5_mock_agents.json"),
    ),
]

API_GOLDEN_CASES = [
    (
        Path(
            "data/raw/fhir_ehr_synthea/samples_100/"
            "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
        ),
        Path("tests/golden/Berna338_Moore224_api_phase5_mock_agents.json"),
    ),
    (
        Path(
            "data/raw/fhir_ehr_synthea/samples_100/"
            "Kris249_Moore224_45dff467-def6-2132-a03a-5950e203b5c8.json"
        ),
        Path("tests/golden/Kris249_Moore224_api_phase5_mock_agents.json"),
    ),
]


@pytest.mark.parametrize("patient_path,golden_path", GOLDEN_CASES)
def test_golden_phase6(patient_path: Path, golden_path: Path) -> None:
    if not patient_path.exists():
        pytest.skip("sample data not available")
    if not golden_path.exists():
        pytest.skip("golden file not available")

    expected = normalize_result(json.loads(golden_path.read_text(encoding="utf-8")))
    actual = normalize_result(generate_result_json(patient_path))
    matches, message = compare_json(expected, actual, fixture_name=golden_path.stem)
    if not matches:
        raise AssertionError(message)


@pytest.mark.parametrize("patient_path,golden_path", API_GOLDEN_CASES)
def test_golden_phase6_api(patient_path: Path, golden_path: Path) -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi test client not available")

    from apps.api.main import app

    if not patient_path.exists():
        pytest.skip("sample data not available")
    if not golden_path.exists():
        pytest.skip("golden file not available")

    client = TestClient(app)
    response = client.post(
        "/v1/analyze",
        json={"path": str(patient_path), "mode": "mock", "enable_agents": True},
    )
    assert response.status_code == 200

    expected = normalize_result(json.loads(golden_path.read_text(encoding="utf-8")))
    actual = normalize_result(response.json())
    matches, message = compare_json(expected, actual, fixture_name=golden_path.stem)
    if not matches:
        raise AssertionError(message)
