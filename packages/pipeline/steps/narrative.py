from __future__ import annotations

import json
import os
import re
import sys
from typing import Optional

from packages.core.llm import LLMClient
from packages.core.schemas.output import NarrativeSummary


def _split_section(snapshot_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"problems": [], "medications": [], "vitals": [], "risks": []}
    current = None
    for line in snapshot_text.splitlines():
        if line.startswith("Recent problems:"):
            current = "problems"
            continue
        if line.startswith("Medications:"):
            current = "medications"
            continue
        if line.startswith("Key vitals/labs:"):
            current = "vitals"
            continue
        if line.startswith("Risks:"):
            current = "risks"
            continue
        if current:
            sections[current].append(line)
    return sections


def _extract_srcs(line: str) -> tuple[str, list[str]]:
    if " | src:" not in line:
        return line, []
    prefix, src = line.split(" | src:", 1)
    citation = src.strip()
    return prefix, [citation] if citation else []


def _mock_narrative(snapshot_text: str, patient_id: str) -> NarrativeSummary:
    sections = _split_section(snapshot_text)
    citations: dict[str, list[str]] = {}
    summary_bullets: list[str] = []
    risk_bullets: list[str] = []

    bullet_id = 1
    for line in sections["problems"][:3]:
        text, _ = _extract_srcs(line)
        summary_bullets.append(f"Recent problem: {text}. [S{bullet_id}]")
        citations[f"S{bullet_id}"] = []
        bullet_id += 1
    for line in sections["medications"][:3]:
        text, _ = _extract_srcs(line)
        summary_bullets.append(f"Medication: {text}. [S{bullet_id}]")
        citations[f"S{bullet_id}"] = []
        bullet_id += 1
    for line in sections["vitals"][:5]:
        text, srcs = _extract_srcs(line)
        summary_bullets.append(f"Key vital/lab: {text}. [S{bullet_id}]")
        citations[f"S{bullet_id}"] = srcs
        bullet_id += 1

    risk_id = 1
    current_risk = None
    current_sources: list[str] = []
    for line in sections["risks"]:
        if line.startswith("  - src:"):
            current_sources.append(line.replace("  - src: ", "").strip())
            continue
        if current_risk is not None:
            risk_bullets.append(f"{current_risk} [R{risk_id}]")
            citations[f"R{risk_id}"] = current_sources
            risk_id += 1
            current_sources = []
        current_risk = line
    if current_risk is not None:
        risk_bullets.append(f"{current_risk} [R{risk_id}]")
        citations[f"R{risk_id}"] = current_sources

    followup_questions = []
    if not risk_bullets:
        followup_questions.append("Any new symptoms or concerns since last visit?")
    else:
        followup_questions.append("Are there symptoms related to the listed risks?")

    return NarrativeSummary(
        patient_id=patient_id,
        summary_bullets=summary_bullets,
        risk_bullets=risk_bullets,
        followup_questions=followup_questions,
        citations=citations,
    )


def _llm_prompt(snapshot_text: str) -> str:
    return (
        "You will be given a deterministic clinical snapshot.\n"
        "Rules:\n"
        "- Do NOT add facts not explicitly present in snapshot_text.\n"
        "- Summary bullets must end with [S#]; risk bullets must end with [R#].\n"
        "- Follow-up questions must NOT include citation tags.\n"
        "- Only cite IDs that appear verbatim in snapshot_text after 'src:'.\n"
        "- Do NOT use '...' anywhere.\n"
        "- If you cannot cite, write 'not documented in provided record' and leave citations empty.\n"
        '- If unsure, say "not documented in provided record".\n'
        "Return ONLY valid JSON. No markdown. No code fences. No commentary.\n"
        "JSON schema:\n"
        '{"patient_id":"<str>",'
        '"summary_bullets":["- ... [S1]"],'
        '"risk_bullets":["- ... [R1]"],'
        '"followup_questions":["- ..."],'
        '"citations":{"S1":["Observation/abc123"]}}\n'
        "snapshot_text:\n"
        f"{snapshot_text}"
    )


def generate_narrative(
    snapshot_text: str, patient_id: str, llm: Optional[LLMClient]
) -> NarrativeSummary:
    if llm is None or not llm.is_available() or not os.getenv("OPENAI_API_KEY"):
        return _mock_narrative(snapshot_text, patient_id)

    prompt = _llm_prompt(snapshot_text)
    try:
        response = llm.complete(prompt)
    except RuntimeError as exc:
        print(f"LLM exception: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise

    try:
        payload = json.loads(response)
        narrative = NarrativeSummary(**payload)
    except Exception as exc:
        preview = response[:800]
        raise RuntimeError(
            "LLM returned non-JSON output: "
            f"{type(exc).__name__}: {exc}. raw_output_preview={preview!r}"
        ) from exc

    bullet_ids = set(
        re.findall(
            r"\[(?:S|R)\d+\]",
            "\n".join(narrative.summary_bullets + narrative.risk_bullets),
        )
    )
    missing_ids = [bid for bid in bullet_ids if bid.strip("[]") not in narrative.citations]

    followup_tags = re.findall(r"\[[^\]]+\]", "\n".join(narrative.followup_questions))
    if followup_tags:
        preview = response[:800]
        raise RuntimeError(
            "LLM citation validation failed: followups must not include citation tags. "
            f"found_tags={followup_tags} raw_output_preview={preview!r}"
        )

    invalid_citations: dict[str, list[str]] = {}
    for key, values in narrative.citations.items():
        bad = []
        for value in values:
            if "..." in value or not re.match(r"^[A-Za-z]+/[A-Za-z0-9\-\.]+$", value):
                bad.append(value)
        if bad:
            invalid_citations[key] = bad

    if missing_ids or invalid_citations:
        preview = response[:800]
        raise RuntimeError(
            "LLM citation validation failed: "
            f"missing_ids={missing_ids} invalid_citations={invalid_citations} "
            f"raw_output_preview={preview!r}"
        )

    return narrative
