from __future__ import annotations

import argparse
import sys

from packages.core.schemas.result import PatientAnalysisResult
from packages.pipeline.steps.snapshot import build_snapshot


def _result_to_json(result: PatientAnalysisResult) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    return result.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic snapshot.")
    parser.add_argument("path", help="Path to patient JSON bundle.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    snapshot_text = build_snapshot(args.path)
    if not args.json:
        print(snapshot_text)
        return 0

    patient_id = "unknown"
    if snapshot_text.startswith("Patient:"):
        patient_id = snapshot_text.split(" | ", 1)[0].replace("Patient: ", "").strip() or "unknown"

    result = PatientAnalysisResult(
        snapshot=snapshot_text,
        risks=[],
        narrative=None,
        meta={"patient_id": patient_id, "source_path": args.path, "mode": "snapshot"},
    )
    print(_result_to_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
