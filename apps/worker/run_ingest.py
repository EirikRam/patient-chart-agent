from __future__ import annotations

import os
import sys
from pathlib import Path

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.steps.timeline import build_timeline


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python apps/worker/run_ingest.py <patient_dir>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    resources = load_patient_dir(path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    print(f"patient_id: {chart.patient_id}")
    print(f"demographics: {len(chart.demographics)}")
    print(f"conditions: {len(chart.conditions)}")
    print(f"medications: {len(chart.medications)}")
    print(f"observations: {len(chart.observations)}")
    print(f"encounters: {len(chart.encounters)}")
    print(f"allergies: {len(chart.allergies)}")

    timeline = build_timeline(chart)
    for event in timeline[:15]:
        date = event["date"].strftime("%Y-%m-%d")
        kind = event["kind"].upper()
        label = event["label"]
        print(f"{date} | {kind} | {label}")
        sources = event.get("sources") or []
        for source in sources[:2]:
            resource_id = source.resource_id
            if resource_id:
                resource_ref = f"{source.resource_type or 'unknown'}/{resource_id}"
            else:
                resource_ref = source.doc_id or "unknown"
            file_path = source.file_path or ""
            if file_path:
                basename = os.path.basename(file_path)
                if not basename:
                    basename = file_path
                print(f"  - src: {resource_ref} ({basename})")
            else:
                print(f"  - src: {resource_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())