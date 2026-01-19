from apps.client.analyze_client import build_payload, format_pretty


def test_build_payload() -> None:
    payload = build_payload("data/sample.json", "mock")
    assert payload == {"path": "data/sample.json", "mode": "mock"}


def test_format_pretty_smoke() -> None:
    result = {
        "snapshot": "Patient: test | sex=unknown | age=unknown | last_seen=unknown",
        "risks": [
            {
                "rule_id": "lab_trend_creatinine",
                "severity": "medium",
                "message": "test risk",
                "evidence": [{"resource_type": "Observation", "resource_id": "obs1"}],
            }
        ],
    }
    text = format_pretty(result)
    assert "Patient: test" in text
    assert "lab_trend_creatinine" in text
