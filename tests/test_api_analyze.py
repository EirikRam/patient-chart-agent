from pathlib import Path

import pytest


def test_analyze_route_smoke() -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi test client not available")

    from apps.api.main import app

    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    client = TestClient(app)
    response = client.post("/v1/analyze", json={"path": str(sample_path), "mode": "mock"})
    assert response.status_code == 200
    payload = response.json()
    assert "snapshot" in payload and payload["snapshot"]
    risks = payload.get("risks") or []
    if risks and risks[0].get("evidence"):
        evidence = risks[0]["evidence"][0]
        assert evidence.get("file_path") == str(sample_path)
        if "timestamp" in evidence:
            assert evidence["timestamp"] is None or isinstance(evidence["timestamp"], str)
