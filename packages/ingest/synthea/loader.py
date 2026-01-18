from __future__ import annotations

import json
from pathlib import Path


def load_patient_dir(path: Path) -> list[dict]:
    """Load JSON resources from a Synthea patient directory or bundle file."""
    if not path.exists():
        raise FileNotFoundError(f"Patient path not found: {path}")

    if path.is_file():
        with path.open("r", encoding="utf-8") as handle:
            return [{"file_path": str(path), "payload": json.load(handle), "input_kind": "file"}]

    if not path.is_dir():
        raise FileNotFoundError(f"Patient directory not found: {path}")

    resources: list[dict] = []
    for file_path in sorted(path.glob("*.json")):
        with file_path.open("r", encoding="utf-8") as handle:
            resources.append(
                {"file_path": str(file_path), "payload": json.load(handle), "input_kind": "dir"}
            )
    return resources