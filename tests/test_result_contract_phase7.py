from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from packages.pipeline.agent_pipeline import run_agent_pipeline
from tests.contract_invariants import (
    assert_agents_disabled_shape,
    assert_agents_enabled_shape,
    assert_base_shape,
    assert_meta_mode,
)

PATIENT_CASES = [
    Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    ),
]

CONTRACT_CASES = [
    ("mock", False),
    ("mock", True),
    ("llm", False),
    ("llm", True),
]


def _result_to_payload(result: object) -> dict:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return json.loads(result.json())


def _assert_narrative_shape(payload: dict, *, expect_null: bool) -> None:
    assert "narrative" in payload
    narrative = payload.get("narrative")
    if expect_null:
        assert narrative is None
        return
    assert isinstance(narrative, dict)
    assert isinstance(narrative.get("patient_id"), str)
    assert isinstance(narrative.get("summary_bullets"), list)
    assert isinstance(narrative.get("risk_bullets"), list)
    assert isinstance(narrative.get("followup_questions"), list)
    assert isinstance(narrative.get("citations"), dict)


def _assert_contract(payload: dict, *, mode: str, agents_enabled: bool, narrative_null: bool) -> None:
    assert_meta_mode(payload, mode)
    assert_base_shape(payload)
    _assert_narrative_shape(payload, expect_null=narrative_null)
    if agents_enabled:
        assert_agents_enabled_shape(payload, mode=mode)
    else:
        assert_agents_disabled_shape(payload)


def _run_cli(patient_path: Path, mode: str, phase5: bool) -> dict:
    args = [
        sys.executable,
        "apps/worker/run_analyze.py",
        str(patient_path),
        "--mode",
        mode,
        "--json",
    ]
    if phase5:
        args.append("--phase5")
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = ""
    result = subprocess.run(args, capture_output=True, text=True, env=env)
    assert result.returncode == 0, (
        f"CLI failed: code={result.returncode}\n"
        f"stdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )
    stdout = result.stdout.strip()
    assert stdout, "CLI returned empty stdout"
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        preview = stdout[:1000]
        raise AssertionError(f"CLI output is not valid JSON: {preview}") from exc


@pytest.mark.parametrize("patient_path", PATIENT_CASES)
@pytest.mark.parametrize("mode,enable_agents", CONTRACT_CASES)
def test_pipeline_result_contract_phase7(
    patient_path: Path, mode: str, enable_agents: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not patient_path.exists():
        pytest.skip("sample data not available")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    result = run_agent_pipeline(patient_path, enable_agents=enable_agents, mode=mode)
    payload = _result_to_payload(result)
    _assert_contract(
        payload, mode=mode, agents_enabled=enable_agents, narrative_null=False
    )


@pytest.mark.parametrize("patient_path", PATIENT_CASES)
@pytest.mark.parametrize("mode,enable_agents", CONTRACT_CASES)
def test_api_result_contract_phase7(
    patient_path: Path, mode: str, enable_agents: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi test client not available")

    if not patient_path.exists():
        pytest.skip("sample data not available")

    monkeypatch.setenv("OPENAI_API_KEY", "")
    from apps.api.main import app

    client = TestClient(app)
    response = client.post(
        "/v1/analyze",
        json={"path": str(patient_path), "mode": mode, "enable_agents": enable_agents},
    )
    assert response.status_code == 200
    payload = response.json()
    _assert_contract(
        payload, mode=mode, agents_enabled=enable_agents, narrative_null=False
    )


@pytest.mark.parametrize("patient_path", PATIENT_CASES)
@pytest.mark.parametrize("mode,phase5", CONTRACT_CASES)
def test_cli_result_contract_phase7(
    patient_path: Path, mode: str, phase5: bool
) -> None:
    if not patient_path.exists():
        pytest.skip("sample data not available")

    payload = _run_cli(patient_path, mode, phase5)
    _assert_contract(
        payload, mode=mode, agents_enabled=phase5, narrative_null=not phase5
    )
