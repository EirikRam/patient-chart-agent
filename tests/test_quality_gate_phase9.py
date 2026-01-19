from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess


def _load_quality_gate():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "quality_gate.py"
    spec = importlib.util.spec_from_file_location("quality_gate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load quality_gate module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quality_gate_all_pass(monkeypatch, capsys) -> None:
    gate = _load_quality_gate()
    calls = []

    def fake_run(command, text, capture_output):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    exit_code = gate.main([])

    assert exit_code == 0
    assert len(calls) == len(gate.STEPS)
    output = capsys.readouterr().out
    assert "PASS: Pytest (full)" in output


def test_quality_gate_failure_includes_step_name(monkeypatch, capsys) -> None:
    gate = _load_quality_gate()
    calls = []

    def fake_run(command, text, capture_output):
        calls.append(command)
        returncode = 1 if len(calls) == 2 else 0
        return subprocess.CompletedProcess(command, returncode, stdout="fail\n", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    exit_code = gate.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "FAIL: Pytest (golden phase 6)" in output


def test_quality_gate_truncates_output(monkeypatch, capsys) -> None:
    gate = _load_quality_gate()
    lines = [f"line {index}" for index in range(1, 101)]
    long_output = "\n".join(lines)

    def fake_run(command, text, capture_output):
        return subprocess.CompletedProcess(command, 1, stdout=long_output, stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    exit_code = gate.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "line 20" not in output
    assert "line 21" in output
    assert "line 100" in output
