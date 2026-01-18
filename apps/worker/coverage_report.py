from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthea dataset coverage report.")
    parser.add_argument("path", type=Path, help="Directory of Synthea bundle JSON files.")
    parser.add_argument("--limit", type=int, default=0, help="Max files to scan (0 = no limit).")
    return parser.parse_args()


def _first(items: Any) -> Optional[dict]:
    if isinstance(items, list) and items:
        item = items[0]
        return item if isinstance(item, dict) else None
    return None


def _codeable_concept(resource: dict, field: str) -> Optional[dict]:
    concept = resource.get(field)
    return concept if isinstance(concept, dict) else None


def _codings(concept: Optional[dict]) -> list[dict]:
    if not concept:
        return []
    codings = concept.get("coding")
    return codings if isinstance(codings, list) else []


def _select_coding(codings: list[dict], prefer: str) -> Optional[dict]:
    prefer_lower = prefer.lower()
    for coding in codings:
        system = coding.get("system")
        if isinstance(system, str) and prefer_lower in system.lower():
            return coding
    return _first(codings)


def _concept_display(concept: Optional[dict], coding: Optional[dict]) -> Optional[str]:
    if coding:
        display = coding.get("display")
        if isinstance(display, str) and display:
            return display
    text = concept.get("text") if concept else None
    return text if isinstance(text, str) and text else None


def _coding_key(coding: Optional[dict]) -> Optional[str]:
    if not coding:
        return None
    system = coding.get("system")
    code = coding.get("code")
    if isinstance(system, str) and isinstance(code, str) and system and code:
        return f"{system}|{code}"
    if isinstance(code, str) and code:
        return code
    return None


def _sorted_counts(counter: Counter[str], limit: int) -> Iterable[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def main() -> int:
    args = parse_args()
    if not args.path.exists() or not args.path.is_dir():
        print(f"Directory not found: {args.path}", file=sys.stderr)
        return 1

    files = sorted(args.path.glob("*.json"))
    if args.limit > 0:
        files = files[: args.limit]

    total_scanned = 0
    failures = 0

    obs_total = 0
    obs_with_coding = 0
    obs_code_counts: Counter[str] = Counter()
    obs_display_counts: Counter[str] = Counter()

    med_total = 0
    med_with_coding = 0
    med_code_counts: Counter[str] = Counter()
    med_display_counts: Counter[str] = Counter()

    allergy_total = 0
    encounter_total = 0
    encounter_display_counts: Counter[str] = Counter()

    for file_path in files:
        total_scanned += 1
        try:
            resources = load_patient_dir(file_path)
            grouped = parse_fhir_resources(resources)
            _ = normalize_to_patient_chart(grouped)
        except Exception:
            failures += 1
            continue

        for item in grouped.get("Observation", []):
            resource = item.get("resource", item)
            if not isinstance(resource, dict):
                continue
            obs_total += 1
            concept = _codeable_concept(resource, "code")
            codings = _codings(concept)
            if any(
                isinstance(coding.get("system"), str) and isinstance(coding.get("code"), str)
                for coding in codings
            ):
                obs_with_coding += 1
            coding = _select_coding(codings, "loinc")
            code_key = _coding_key(coding)
            if code_key:
                obs_code_counts[code_key] += 1
            display = _concept_display(concept, coding)
            if display:
                obs_display_counts[display] += 1

        for key in ("MedicationRequest", "MedicationStatement"):
            for item in grouped.get(key, []):
                resource = item.get("resource", item)
                if not isinstance(resource, dict):
                    continue
                med_total += 1
                concept = _codeable_concept(resource, "medicationCodeableConcept")
                codings = _codings(concept)
                if any(
                    isinstance(coding.get("system"), str) and isinstance(coding.get("code"), str)
                    for coding in codings
                ):
                    med_with_coding += 1
                coding = _select_coding(codings, "rxnorm")
                code_key = _coding_key(coding)
                if code_key:
                    med_code_counts[code_key] += 1
                display = _concept_display(concept, coding)
                if display:
                    med_display_counts[display] += 1

        allergy_total += len(grouped.get("AllergyIntolerance", []))

        for item in grouped.get("Encounter", []):
            resource = item.get("resource", item)
            if not isinstance(resource, dict):
                continue
            encounter_total += 1
            for field in ("reasonCode", "type"):
                concept = _first(resource.get(field)) if field in resource else None
                if not concept:
                    continue
                codings = _codings(concept)
                coding = _select_coding(codings, "")
                display = _concept_display(concept, coding)
                if display:
                    encounter_display_counts[display] += 1

    print(f"files scanned: {total_scanned}")
    if failures:
        print(f"failures: {failures}")

    obs_pct = (obs_with_coding / obs_total * 100) if obs_total else 0.0
    med_pct = (med_with_coding / med_total * 100) if med_total else 0.0

    print(f"observations: {obs_total}")
    print(f"observations with coding: {obs_with_coding} ({obs_pct:.1f}%)")
    print(f"medications: {med_total}")
    print(f"medications with coding: {med_with_coding} ({med_pct:.1f}%)")
    print(f"allergies: {allergy_total}")
    print(f"encounters: {encounter_total}")

    print("top observation codes:")
    for code, count in _sorted_counts(obs_code_counts, 20):
        print(f"  {code}: {count}")
    print("top observation displays:")
    for display, count in _sorted_counts(obs_display_counts, 20):
        print(f"  {display}: {count}")

    print("top medication codes:")
    for code, count in _sorted_counts(med_code_counts, 20):
        print(f"  {code}: {count}")
    print("top medication displays:")
    for display, count in _sorted_counts(med_display_counts, 20):
        print(f"  {display}: {count}")

    print("top encounter reason/type displays:")
    for display, count in _sorted_counts(encounter_display_counts, 20):
        print(f"  {display}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
