from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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
@pytest.mark.parametrize("mode,phase5", CONTRACT_CASES)
def test_cli_contract_matrix_phase6(
    patient_path: Path, mode: str, phase5: bool
) -> None:
    if not patient_path.exists():
        pytest.skip("sample data not available")

    payload = _run_cli(patient_path, mode, phase5)
    assert_meta_mode(payload, mode)
    assert_base_shape(payload)
    if not phase5:
        assert_agents_disabled_shape(payload)
    else:
        assert_agents_enabled_shape(payload, mode=mode)
