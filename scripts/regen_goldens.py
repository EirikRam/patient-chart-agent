from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.golden.utils import generate_result_json, normalize_result, write_json_pretty


GOLDEN_OUTPUTS = [
    Path("tests/golden/Berna338_Moore224_phase5_mock_agents.json"),
    Path("tests/golden/Kris249_Moore224_phase5_mock_agents.json"),
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


def main() -> int:
    args = _parse_args()
    if not args.force:
        print("Refusing to regenerate goldens without --force.")
        return 1

    cases = [
        (args.berna_path, GOLDEN_OUTPUTS[0]),
        (args.kris_path, GOLDEN_OUTPUTS[1]),
    ]
    for patient_path, golden_path in cases:
        if not patient_path.exists():
            print(f"Input bundle not found: {patient_path}")
            return 1
        result = generate_result_json(patient_path)
        normalized = normalize_result(result)
        write_json_pretty(golden_path, normalized)
        print(f"Wrote {golden_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
