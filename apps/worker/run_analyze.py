from __future__ import annotations

import sys
from pathlib import Path

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.steps.risks import run_risk_rules


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python apps/worker/run_analyze.py <patient.json>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    resources = load_patient_dir(path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    risks = run_risk_rules(chart)
    if not risks:
        print("0 risks found")
        return 0

    print(f"total risks found: {len(risks)}")
    for risk in risks:
        rule_id = risk.get("rule_id", "unknown")
        severity = risk.get("severity", "medium")
        message = risk.get("message", "")
        print(f"{rule_id} | {severity} | {message}")
        evidence = risk.get("evidence") or []
        for source in evidence[:5]:
            resource_type = getattr(source, "resource_type", None) or "unknown"
            resource_id = getattr(source, "resource_id", None) or "unknown"
            print(f"  - src: {resource_type}/{resource_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())