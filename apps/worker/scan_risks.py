from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.steps.risks import run_risk_rules
from packages.risklib.rules import discover_rules


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Synthea bundles for risk rules.")
    parser.add_argument("path", type=Path, help="Directory of Synthea bundle JSON files.")
    parser.add_argument("--limit", type=int, default=0, help="Max files to scan (0 = no limit).")
    parser.add_argument(
        "--max-per-rule",
        type=int,
        default=3,
        help="Max example patient_ids to keep per rule.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print per-file errors.")
    parser.add_argument("--debug", action="store_true", help="Summarize rule debug reasons.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.path.exists() or not args.path.is_dir():
        print(f"Directory not found: {args.path}", file=sys.stderr)
        return 1

    files = sorted(args.path.glob("*.json"))
    if args.limit > 0:
        files = files[: args.limit]

    total_scanned = 0
    patients_with_risks = 0
    failures = 0
    rule_counts: dict[str, int] = {}
    rule_examples: dict[str, list[str]] = {}
    debug_counts: dict[str, dict[str, int]] = {}
    rule_names: list[str] = []
    if args.debug:
        runners = discover_rules()
        rule_names = sorted(runners.keys())
        print(f"rules loaded: {len(rule_names)}")
        print(f"rules: {', '.join(rule_names)}")

    for file_path in files:
        total_scanned += 1
        try:
            resources = load_patient_dir(file_path)
            grouped = parse_fhir_resources(resources)
            chart = normalize_to_patient_chart(grouped)
            if args.debug:
                risks, debug_info = run_risk_rules(chart, debug=True)
                for rule_id, reason in sorted(debug_info.items()):
                    rule_reasons = debug_counts.setdefault(rule_id, {})
                    rule_reasons[reason] = rule_reasons.get(reason, 0) + 1
            else:
                risks = run_risk_rules(chart)
        except Exception as exc:
            failures += 1
            if args.verbose:
                print(f"failed: {file_path} ({exc})", file=sys.stderr)
            continue

        if not risks:
            continue

        patients_with_risks += 1
        patient_id = chart.patient_id
        for risk in risks:
            rule_id = risk.get("rule_id", "unknown")
            rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
            examples = rule_examples.setdefault(rule_id, [])
            if patient_id not in examples and len(examples) < args.max_per_rule:
                examples.append(patient_id)

    print(f"total files scanned: {total_scanned}")
    print(f"total patients with >=1 risk: {patients_with_risks}")
    if failures:
        print(f"failures: {failures}")

    rule_ids = sorted(rule_names or rule_counts.keys())
    for rule_id in rule_ids:
        count = rule_counts.get(rule_id, 0)
        examples = ", ".join(rule_examples.get(rule_id, []))
        print(f"{rule_id}: {count} (examples: {examples})")

    if args.debug:
        for rule_id in rule_ids:
            reason_counts = debug_counts.get(rule_id, {})
            sorted_reasons = sorted(
                reason_counts.items(), key=lambda item: (-item[1], item[0])
            )[:3]
            reasons_text = ", ".join([f"{reason} ({count})" for reason, count in sorted_reasons])
            print(f"{rule_id} reasons: {reasons_text}")
            print(f"{rule_id} executed=True, hits={rule_counts.get(rule_id, 0)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
