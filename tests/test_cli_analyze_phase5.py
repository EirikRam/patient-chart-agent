import json
import sys
from pathlib import Path

import pytest

from apps.worker import run_analyze


def test_run_analyze_phase5_json(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    monkeypatch.setattr(sys, "argv", ["run_analyze.py", str(sample_path), "--json", "--phase5"])
    exit_code = run_analyze.main()
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload.get("timeline") is not None


def test_run_analyze_accepts_mode_arg(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    monkeypatch.setattr(sys, "argv", ["run_analyze.py", str(sample_path), "--json", "--mode", "mock"])
    exit_code = run_analyze.main()
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload.get("meta", {}).get("mode") == "mock"


def test_run_analyze_llm_mode_without_keys_returns_safe_json(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    monkeypatch.setattr(sys, "argv", ["run_analyze.py", str(sample_path), "--json", "--mode", "llm"])
    exit_code = run_analyze.main()
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload.get("meta", {}).get("mode") == "llm"
    assert "snapshot" in payload
    assert "risks" in payload
    assert "meta" in payload
    assert payload.get("narrative") is None
