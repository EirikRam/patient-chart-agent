from __future__ import annotations

import json
import sys
from pathlib import Path


def _bundle_has_patient(payload: dict, patient_id: str) -> bool:
    if payload.get("resourceType") != "Bundle":
        return False
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") == "Patient":
            if resource.get("id") == patient_id:
                return True
    return False


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python apps/worker/find_patient_file.py <dir> <patient_id>", file=sys.stderr)
        return 1

    root = Path(sys.argv[1])
    patient_id = sys.argv[2]
    if not root.exists() or not root.is_dir():
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    for file_path in sorted(root.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and _bundle_has_patient(payload, patient_id):
            print(str(file_path))
            return 0

    print("not found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
