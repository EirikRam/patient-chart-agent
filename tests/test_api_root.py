from fastapi.testclient import TestClient

from apps.api.main import app


def test_root() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "patient-chart-agent"
    assert payload["status"] == "ok"
    assert payload["endpoints"] == ["/healthz", "/readyz", "/v1/analyze"]
