from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.golden.utils import generate_result_json, normalize_result, write_json_pretty


PIPELINE_OUTPUTS = [
    Path("tests/golden/Berna338_Moore224_phase5_mock_agents.json"),
    Path("tests/golden/Kris249_Moore224_phase5_mock_agents.json"),
]
API_OUTPUTS = [
    Path("tests/golden/Berna338_Moore224_api_phase5_mock_agents.json"),
    Path("tests/golden/Kris249_Moore224_api_phase5_mock_agents.json"),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate golden fixtures (explicit, guarded)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actually write golden outputs.",
    )
    parser.add_argument(
        "berna_path",
        type=Path,
        help="Path to Berna338_Moore224 bundle JSON.",
    )
    parser.add_argument(
        "kris_path",
        type=Path,
        help="Path to Kris249_Moore224 bundle JSON.",
    )
    return parser.parse_args()


def _looks_like_golden(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith("_phase5_mock_agents.json"):
        return True
    parts = {part.lower() for part in path.parts}
    return "tests" in parts and "golden" in parts


def main() -> int:
    args = _parse_args()
    if not args.force:
        print("Refusing to regenerate goldens without --force.")
        return 1

    try:
        from fastapi.testclient import TestClient
    except Exception as exc:
        print(f"FastAPI TestClient not available: {exc}")
        return 1

    from apps.api.main import app

    client = TestClient(app)
    pipeline_cases = [
        (args.berna_path, PIPELINE_OUTPUTS[0]),
        (args.kris_path, PIPELINE_OUTPUTS[1]),
    ]
    api_cases = [
        (args.berna_path, API_OUTPUTS[0]),
        (args.kris_path, API_OUTPUTS[1]),
    ]
    for patient_path in (args.berna_path, args.kris_path):
        if not os.path.exists(patient_path):
            print(f"Input bundle not found: {patient_path}")
            return 1
        if _looks_like_golden(patient_path):
            print(
                "Refusing to use golden fixture as input. "
                "Please pass bundle paths under data/raw/..."
            )
            return 1

    written: list[Path] = []
    for patient_path, golden_path in pipeline_cases:
        result = generate_result_json(patient_path)
        normalized = normalize_result(result)
        write_json_pretty(golden_path, normalized)
        written.append(golden_path)

    for patient_path, golden_path in api_cases:
        payload = {"path": str(patient_path), "mode": "mock", "enable_agents": True}
        response = client.post("/v1/analyze", json=payload)
        if response.status_code != 200:
            print(f"API request failed for {patient_path}: {response.status_code}")
            return 1
        normalized = normalize_result(response.json())
        write_json_pretty(golden_path, normalized)
        written.append(golden_path)
    print("Wrote golden fixtures:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
