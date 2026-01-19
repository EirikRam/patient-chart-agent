from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packages.core.llm import LLMClient
import re

from packages.pipeline.steps.narrative import generate_narrative
from packages.pipeline.steps.snapshot import build_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate grounded narrative.")
    parser.add_argument("path", type=Path, help="Path to patient JSON bundle.")
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock")
    return parser.parse_args()


def _print_narrative(narrative) -> None:
    print(f"patient_id: {narrative.patient_id}")
    print("Summary:")
    for bullet in narrative.summary_bullets:
        print(f"- {bullet}")
        match = re.search(r"\[(S\d+)\]", bullet)
        if match:
            cites = narrative.citations.get(match.group(1), [])
            for cite in cites:
                print(f"  - src: {cite}")
    print("Risks:")
    for bullet in narrative.risk_bullets:
        print(f"- {bullet}")
        match = re.search(r"\[(R\d+)\]", bullet)
        if match:
            cites = narrative.citations.get(match.group(1), [])
            for cite in cites:
                print(f"  - src: {cite}")
    print("Follow-up questions:")
    for question in narrative.followup_questions:
        print(f"- {question}")
        match = re.search(r"\[(F\d+)\]", question)
        if match:
            cites = narrative.citations.get(match.group(1), [])
            for cite in cites:
                print(f"  - src: {cite}")


def main() -> int:
    args = parse_args()
    if not args.path.exists():
        print(f"File not found: {args.path}", file=sys.stderr)
        return 1

    snapshot_text = build_snapshot(str(args.path))
    patient_id = "unknown"
    if snapshot_text.startswith("Patient:"):
        first_line = snapshot_text.splitlines()[0]
        patient_id = first_line.split(" | ", 1)[0].replace("Patient: ", "").strip() or "unknown"
    llm = LLMClient() if args.mode == "llm" else None
    if llm is not None:
        print(f"LLM mode enabled: model={llm.model} base_url={llm.base_url}")
    try:
        narrative = generate_narrative(snapshot_text, patient_id, llm)
    except Exception as exc:
        print(f"LLM failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Falling back to mock mode.", file=sys.stderr)
        narrative = generate_narrative(snapshot_text, patient_id, None)
    _print_narrative(narrative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
