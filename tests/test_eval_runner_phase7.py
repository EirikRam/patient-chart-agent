from __future__ import annotations

import json
import os
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
    _apply_llm_ok_rate_gate,
    _build_json_payload,
    _failure_counts_sorted,
    _llm_ok_rate,
)

MANIFEST_PATH = Path("eval/manifest.json")


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
    assert manifest.get("version") == "phase8.1"
    assert manifest.get("mode") == "mock"
    assert manifest.get("enable_agents") is True
    patients = manifest.get("patients", [])
    assert isinstance(patients, list)
    assert len(patients) >= 10


def test_eval_runner_phase7_metrics_shape() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")

    report = evaluate_manifest(MANIFEST_PATH)
    assert report.get("version") == "phase8.1"
    assert report.get("mode") == "mock"
    assert report.get("enable_agents") is True
    patients = report.get("patients", [])
    assert isinstance(patients, list)
    assert len(patients) >= 10
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


def _run_eval_cli(
    args: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "eval.run_eval"] + args,
        capture_output=True,
        text=True,
        env=env,
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


def test_eval_cli_llm_skips_without_keys() -> None:
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("AZURE_OPENAI_API_KEY", None)
    env.pop("AZURE_OPENAI_ENDPOINT", None)
    env.pop("AZURE_OPENAI_BASE_URL", None)
    env.pop("AZURE_OPENAI_DEPLOYMENT", None)
    env.pop("AZURE_OPENAI_DEPLOYMENT_NAME", None)
    result = _run_eval_cli(["--modes", "llm", "--quiet"], env=env)
    assert result.returncode == 0
    assert "llm skipped: missing keys" in result.stdout


def test_eval_cli_llm_skips_with_status(tmp_path: Path) -> None:
    manifest = {
        "version": "test",
        "mode": "mock",
        "enable_agents": True,
        "gates": {},
        "patients": [{"name": "TestPatient", "path": "data/does_not_matter.json"}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("AZURE_OPENAI_API_KEY", None)
    env.pop("AZURE_OPENAI_ENDPOINT", None)
    env.pop("AZURE_OPENAI_BASE_URL", None)
    env.pop("AZURE_OPENAI_DEPLOYMENT", None)
    env.pop("AZURE_OPENAI_DEPLOYMENT_NAME", None)
    result = _run_eval_cli(
        ["--manifest", str(manifest_path), "--modes", "llm", "--json"], env=env
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    patient = payload["per_patient"][0]
    llm = patient["modes"]["llm"]
    assert llm["llm_status"] == "skipped"
    assert llm["llm_reason"] == "llm skipped: missing keys"


def test_eval_require_llm_fails_on_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = {
        "version": "test",
        "mode": "mock",
        "enable_agents": True,
        "gates": {},
        "patients": [{"name": "TestPatient", "path": "data/does_not_matter.json"}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    from eval import run_eval

    monkeypatch.setattr(run_eval, "_detect_llm_keys", lambda: (False, "llm skipped: missing keys"))
    report = evaluate_manifest(manifest_path, mode="llm", require_llm=True)
    assert report["overall_pass"] is False
    patient = report["patients"][0]
    assert "llm_required_but_skipped" in patient["failures"]


def test_eval_llm_exception_marks_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {
        "version": "test",
        "mode": "mock",
        "enable_agents": True,
        "gates": {},
        "patients": [{"name": "TestPatient", "path": "data/does_not_matter.json"}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    from eval import run_eval

    monkeypatch.setattr(run_eval, "_detect_llm_keys", lambda: (True, "llm keys: openai"))

    def _raise_timeout(*args: object, **kwargs: object) -> None:
        raise TimeoutError("boom")

    monkeypatch.setattr(run_eval, "_run_llm_with_timeout", _raise_timeout)
    report = evaluate_manifest(manifest_path, mode="llm")
    patient = report["patients"][0]
    assert patient["llm_status"] == "failed"
    assert patient["llm_reason"] == "llm failed: TimeoutError"


def test_failure_counts_sorted_is_stable() -> None:
    counts = {"b_error": 2, "a_error": 2, "c_error": 1}
    ordered = _failure_counts_sorted(counts)
    assert ordered == [("a_error", 2), ("b_error", 2), ("c_error", 1)]


def test_llm_ok_rate_gate_edge_cases() -> None:
    empty_results = [{"llm_status": None, "failures": [], "patient_pass": True}]
    assert _llm_ok_rate(empty_results) == 0.0
    llm_ok_rate, failure = _apply_llm_ok_rate_gate(
        empty_results, {"min_llm_ok_rate": 0.5}, llm_ok_rate=None, apply_gate=False
    )
    assert llm_ok_rate is None
    assert failure is None

    mixed_results = [
        {"llm_status": "ok", "failures": [], "patient_pass": True},
        {"llm_status": "skipped", "failures": [], "patient_pass": True},
    ]
    assert _llm_ok_rate(mixed_results) == 1.0
    llm_ok_rate, failure = _apply_llm_ok_rate_gate(
        mixed_results, {"min_llm_ok_rate": 0.6}, llm_ok_rate=1.0, apply_gate=True
    )
    assert llm_ok_rate == 1.0
    assert failure is None


def test_llm_ok_rate_attempted_zero_is_zero() -> None:
    skipped_only = [{"llm_status": "skipped", "failures": [], "patient_pass": True}]
    assert _llm_ok_rate(skipped_only) == 0.0


def test_json_payload_structure_is_stable() -> None:
    reports = [
        {
            "version": "test",
            "mode": "mock",
            "patients": [
                {
                    "name": "Alice",
                    "path": "x.json",
                    "patient_pass": False,
                    "failures": ["b_error", "a_error"],
                }
            ],
        },
        {
            "version": "test",
            "mode": "llm",
            "patients": [
                {
                    "name": "Alice",
                    "path": "x.json",
                    "patient_pass": True,
                    "failures": [],
                    "llm_status": "ok",
                    "llm_reason": None,
                }
            ],
        },
    ]
    payload = _build_json_payload(reports, require_llm=False)
    assert payload["overall_pass"] is False
    assert payload["patients_failed_count"] == 1
    assert payload["patients_failed"] == ["Alice"]
    assert list(payload["failure_counts"].keys()) == ["a_error", "b_error"]
    per_patient = payload["per_patient"][0]
    assert per_patient["name"] == "Alice"
    assert per_patient["patient_pass"] is False
    assert per_patient["failures"] == ["a_error", "b_error"]
    assert "mock" in per_patient["modes"]
    assert "llm" in per_patient["modes"]


def test_eval_cli_mock_and_llm_skips_without_keys() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    missing = [path for path in _patient_paths(manifest) if not path.exists()]
    if missing:
        pytest.skip("sample data not available")
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("AZURE_OPENAI_API_KEY", None)
    env.pop("AZURE_OPENAI_ENDPOINT", None)
    env.pop("AZURE_OPENAI_BASE_URL", None)
    env.pop("AZURE_OPENAI_DEPLOYMENT", None)
    env.pop("AZURE_OPENAI_DEPLOYMENT_NAME", None)
    result = _run_eval_cli(
        ["--manifest", str(MANIFEST_PATH), "--modes", "mock,llm", "--quiet"],
        env=env,
    )
    assert result.returncode == 0
    assert "mode: mock" in result.stdout
    assert "mode: llm" in result.stdout
    assert "llm skipped: missing keys" in result.stdout


def test_llm_retry_transient_then_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {
        "version": "test",
        "mode": "mock",
        "enable_agents": True,
        "gates": {},
        "patients": [{"name": "TestPatient", "path": "data/does_not_matter.json"}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    from eval import run_eval

    monkeypatch.setattr(run_eval, "_detect_llm_keys", lambda: (True, "llm keys: openai"))
    calls = {"count": 0}

    def _fake_run(*args: object, **kwargs: object) -> PatientAnalysisResult:
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("transient")
        return PatientAnalysisResult(meta={"patient_id": "test", "source_path": "x", "mode": "llm"})

    monkeypatch.setattr(run_eval, "_run_llm_with_timeout", _fake_run)
    report = evaluate_manifest(manifest_path, mode="llm", llm_retries=1)
    patient = report["patients"][0]
    assert patient["llm_status"] == "ok"
    assert report["llm_retried"] == 1


def test_llm_retry_non_transient_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {
        "version": "test",
        "mode": "mock",
        "enable_agents": True,
        "gates": {},
        "patients": [{"name": "TestPatient", "path": "data/does_not_matter.json"}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    from eval import run_eval

    monkeypatch.setattr(run_eval, "_detect_llm_keys", lambda: (True, "llm keys: openai"))

    def _raise_value(*args: object, **kwargs: object) -> None:
        raise ValueError("not transient")

    monkeypatch.setattr(run_eval, "_run_llm_with_timeout", _raise_value)
    report = evaluate_manifest(manifest_path, mode="llm", llm_retries=2)
    patient = report["patients"][0]
    assert patient["llm_status"] == "failed"
    assert patient["llm_reason"] == "llm failed: ValueError"
    assert report["llm_retried"] == 0


def test_llm_retry_exhausted_transient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {
        "version": "test",
        "mode": "mock",
        "enable_agents": True,
        "gates": {},
        "patients": [{"name": "TestPatient", "path": "data/does_not_matter.json"}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    from eval import run_eval

    monkeypatch.setattr(run_eval, "_detect_llm_keys", lambda: (True, "llm keys: openai"))

    def _always_timeout(*args: object, **kwargs: object) -> None:
        raise TimeoutError("still transient")

    monkeypatch.setattr(run_eval, "_run_llm_with_timeout", _always_timeout)
    report = evaluate_manifest(manifest_path, mode="llm", llm_retries=1)
    patient = report["patients"][0]
    assert patient["llm_status"] == "failed"
    assert patient["llm_reason"] == "llm failed: TimeoutError"
    assert report["llm_retried"] == 1
