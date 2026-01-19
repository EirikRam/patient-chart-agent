from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from packages.core.schemas.result import PatientAnalysisResult
from eval.run_eval import (
    evaluate_gates,
    evaluate_manifest,
    load_manifest,
    _score_result,
)

MANIFEST_PATH = Path("eval/manifest_phase7.json")


def _patient_paths(manifest: dict) -> list[Path]:
    patients = manifest.get("patients", [])
    paths: list[Path] = []
    for patient in patients:
        rel_path = patient.get("path", "")
        if rel_path:
            paths.append(Path(rel_path))
    return paths


def test_manifest_loads_phase7() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    assert manifest.get("version") == "phase7.2"
    assert manifest.get("mode") == "mock"
    assert manifest.get("enable_agents") is True
    patients = manifest.get("patients", [])
    assert isinstance(patients, list)
    assert len(patients) == 2


def test_eval_runner_phase7_metrics_shape() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")

    report = evaluate_manifest(MANIFEST_PATH)
    assert report.get("version") == "phase7.2"
    assert report.get("mode") == "mock"
    assert report.get("enable_agents") is True
    patients = report.get("patients", [])
    assert isinstance(patients, list)
    assert len(patients) == 2
    for item in patients:
        assert isinstance(item.get("risk_precision"), float)
        assert isinstance(item.get("risk_recall"), float)
        assert isinstance(item.get("missing_precision"), float)
        assert isinstance(item.get("missing_recall"), float)
        assert isinstance(item.get("contradiction_precision"), float)
        assert isinstance(item.get("contradiction_recall"), float)
        assert isinstance(item.get("risk_tp"), int)
        assert isinstance(item.get("risk_fp"), int)
        assert isinstance(item.get("risk_fn"), int)
        assert isinstance(item.get("missing_tp"), int)
        assert isinstance(item.get("missing_fp"), int)
        assert isinstance(item.get("missing_fn"), int)
        assert isinstance(item.get("contradiction_tp"), int)
        assert isinstance(item.get("contradiction_fp"), int)
        assert isinstance(item.get("contradiction_fn"), int)
        assert isinstance(item.get("strict_fail_risks"), bool)
        assert isinstance(item.get("strict_fail_missing_info"), bool)
        assert isinstance(item.get("strict_fail_contradictions"), bool)
        assert isinstance(item.get("patient_pass"), bool)
        assert isinstance(item.get("failures"), list)
        assert 0.0 <= item.get("risk_precision") <= 1.0
        assert 0.0 <= item.get("risk_recall") <= 1.0
        assert 0.0 <= item.get("missing_precision") <= 1.0
        assert 0.0 <= item.get("missing_recall") <= 1.0
        assert 0.0 <= item.get("contradiction_precision") <= 1.0
        assert 0.0 <= item.get("contradiction_recall") <= 1.0


def test_eval_runner_phase7_expected_ids() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")

    report = evaluate_manifest(MANIFEST_PATH)
    patients = report.get("patients", [])
    assert isinstance(patients, list)
    by_name = {item.get("name"): item for item in patients}

    berna = by_name.get("Berna338")
    assert berna is not None
    expected_risks = set(berna.get("expected_risks", []))
    assert "lab_a1c_elevated" in expected_risks
    assert "lab_trend_potassium" in expected_risks
    assert "vitals_bmi_obesity" in expected_risks
    expected_contradictions = set(berna.get("expected_contradiction_ids", []))
    assert "conflicting_condition_onset" in expected_contradictions

    kris = by_name.get("Kris249")
    assert kris is not None
    assert kris.get("expected_risks") == []
    assert kris.get("expected_missing_info_ids") == []
    assert kris.get("expected_contradiction_ids") == []


def test_allow_extra_defaults_and_strict_fail() -> None:
    result = PatientAnalysisResult(
        risks=[{"rule_id": "extra_risk", "severity": "low", "message": "", "evidence": []}],
        meta={"patient_id": "test", "source_path": "x", "mode": "mock"},
    )
    expects_default = {"risks": []}
    metrics_default = _score_result(result, expects_default)
    assert metrics_default["strict_fail_risks"] is False

    expects_strict = {"risks": [], "allow_extra_risks": False}
    metrics_strict = _score_result(result, expects_strict)
    assert metrics_strict["strict_fail_risks"] is True
    assert metrics_strict["risk_precision"] == 0.0


def test_gates_tightening_causes_fail() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")

    report = evaluate_manifest(MANIFEST_PATH)
    patient = report.get("patients", [])[0]
    gates = report.get("gates", {})
    tightened = dict(gates)
    tightened["min_risk_precision"] = 1.1
    gate_result = evaluate_gates(patient, tightened)
    assert gate_result["patient_pass"] is False
    assert gate_result["failures"]


def test_gate_failure_string_format() -> None:
    metrics = {"risk_precision": 0.5}
    gates = {"min_risk_precision": 0.8}
    result = evaluate_gates(metrics, gates)
    assert result["patient_pass"] is False
    assert result["failures"] == ["risk_precision < 0.80 (0.50)"]


def _run_eval_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "eval.run_eval"] + args,
        capture_output=True,
        text=True,
    )


def test_eval_cli_exit_codes_ok() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")
    result = _run_eval_cli(["--manifest", str(MANIFEST_PATH), "--quiet"])
    assert result.returncode == 0


def test_eval_cli_exit_codes_fail() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")
    tightened = dict(manifest)
    gates = dict(tightened.get("gates", {}))
    gates["min_risk_precision"] = 1.1
    tightened["gates"] = gates
    tmp_path = Path("tests/_tmp_eval_manifest.json")
    tmp_path.write_text(json.dumps(tightened), encoding="utf-8")
    try:
        result = _run_eval_cli(["--manifest", str(tmp_path), "--quiet"])
        assert result.returncode == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_eval_cli_exit_codes_invalid_manifest() -> None:
    result = _run_eval_cli(["--manifest", "nope/does_not_exist.json", "--quiet"])
    assert result.returncode == 2
