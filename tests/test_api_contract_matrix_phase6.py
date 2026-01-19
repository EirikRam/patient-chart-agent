from __future__ import annotations

from pathlib import Path

import pytest

from tests.contract_invariants import (
    assert_agents_disabled_shape,
    assert_agents_enabled_shape,
    assert_base_shape,
    assert_meta_mode,
)
from tests.golden.utils import normalize_result


PATIENT_CASES = [
    Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    ),
    Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Kris249_Moore224_45dff467-def6-2132-a03a-5950e203b5c8.json"
    ),
]

CONTRACT_CASES = [
    ("mock", False),
    ("mock", True),
    ("llm", False),
    ("llm", True),
]


@pytest.mark.parametrize("patient_path", PATIENT_CASES)
@pytest.mark.parametrize("mode,enable_agents", CONTRACT_CASES)
def test_api_contract_matrix_phase6(
    patient_path: Path, mode: str, enable_agents: bool
) -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi test client not available")

    from apps.api.main import app

    if not patient_path.exists():
        pytest.skip("sample data not available")

    client = TestClient(app)
    response = client.post(
        "/v1/analyze",
        json={"path": str(patient_path), "mode": mode, "enable_agents": enable_agents},
    )
    assert response.status_code == 200

    payload = normalize_result(response.json())
    assert_meta_mode(payload, mode)
    assert_base_shape(payload)
    if not enable_agents:
        assert_agents_disabled_shape(payload)
    else:
        assert_agents_enabled_shape(payload, mode=mode)
