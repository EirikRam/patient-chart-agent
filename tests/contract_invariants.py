from __future__ import annotations

from typing import Any


def assert_meta_mode(payload: dict, expected_mode: str) -> None:
    meta = payload.get("meta") or {}
    assert meta.get("mode") == expected_mode
    assert isinstance(meta.get("patient_id"), str)
    assert meta.get("patient_id").strip() != ""


def assert_base_shape(payload: dict) -> None:
    risks = payload.get("risks")
    assert isinstance(risks, list)
    for risk in risks:
        _assert_risk_shape(risk)


def assert_agents_disabled_shape(payload: dict) -> None:
    assert payload.get("timeline") is None
    assert payload.get("missing_info") is None
    assert payload.get("contradictions") is None


def assert_agents_enabled_shape(payload: dict, *, mode: str) -> None:
    timeline = payload.get("timeline")
    missing_info = payload.get("missing_info")
    contradictions = payload.get("contradictions")
    if mode == "mock":
        assert isinstance(timeline, list)
        assert isinstance(missing_info, list)
        assert isinstance(contradictions, list)
        return
    assert timeline is None or isinstance(timeline, list)
    assert missing_info is None or isinstance(missing_info, list)
    assert contradictions is None or isinstance(contradictions, list)


def _assert_risk_shape(risk: Any) -> None:
    assert isinstance(risk, dict)
    assert "rule_id" in risk
    assert "severity" in risk
    assert "message" in risk
    assert "evidence" in risk
    assert isinstance(risk.get("rule_id"), str)
    assert isinstance(risk.get("severity"), str)
    assert isinstance(risk.get("message"), str)
    evidence = risk.get("evidence")
    assert isinstance(evidence, list)
    for item in evidence:
        assert isinstance(item, dict)
        assert "doc_id" in item
        assert "resource_type" in item
        assert "resource_id" in item
        assert "file_path" in item
        if item.get("file_path") is not None:
            assert isinstance(item.get("file_path"), str)
            assert item.get("file_path").strip() != ""
