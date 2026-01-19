import json
from pathlib import Path

import pytest

from tests.golden.utils import (
    compare_json,
    ensure_dir,
    generate_result_json,
    normalize_result,
    write_json_pretty,
)


GOLDEN_CASES = [
    (
        Path(
            "data/raw/fhir_ehr_synthea/samples_100/"
            "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
        ),
        Path("tests/golden/Berna338_Moore224_phase5_mock_agents.json"),
    ),
    (
        Path(
            "data/raw/fhir_ehr_synthea/samples_100/"
            "Kris249_Moore224_45dff467-def6-2132-a03a-5950e203b5c8.json"
        ),
        Path("tests/golden/Kris249_Moore224_phase5_mock_agents.json"),
    ),
]


@pytest.mark.parametrize("patient_path,golden_path", GOLDEN_CASES)
def test_golden_phase6(patient_path: Path, golden_path: Path) -> None:
    if not patient_path.exists():
        pytest.skip("sample data not available")
    if not golden_path.exists():
        pytest.skip("golden file not available")

    expected = normalize_result(json.loads(golden_path.read_text(encoding="utf-8")))
    actual = normalize_result(generate_result_json(patient_path))
    matches, diff = compare_json(expected, actual)
    if not matches:
        out_dir = Path("tests/golden/_out")
        ensure_dir(out_dir)
        actual_path = out_dir / f"actual_{golden_path.stem}.json"
        write_json_pretty(actual_path, actual)
        raise AssertionError(
            "Golden output mismatch. "
            f"Wrote actual output to {actual_path}.\n{diff}"
        )
