from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Optional

from packages.core.schemas.result import PatientAnalysisResult

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _severity_rank(severity: str | None) -> int:
    if not severity:
        return 0
    return _SEVERITY_ORDER.get(severity.lower(), 0)


def _escape_table(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|")


def _get_value(obj: object, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _normalize_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return "unknown"
    return str(value)


def _iter_evidence(items: Iterable[object]) -> Iterable[dict[str, object]]:
    for source in items:
        if isinstance(source, dict):
            yield {
                "resource_type": source.get("resource_type"),
                "resource_id": source.get("resource_id"),
                "timestamp": source.get("timestamp"),
                "file_path": source.get("file_path"),
            }
        else:
            yield {
                "resource_type": getattr(source, "resource_type", None),
                "resource_id": getattr(source, "resource_id", None),
                "timestamp": getattr(source, "timestamp", None),
                "file_path": getattr(source, "file_path", None),
            }


def _collect_citations(result: PatientAnalysisResult) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add_evidence(items: Iterable[object] | None) -> None:
        if not items:
            return
        for evidence in _iter_evidence(items):
            resource_type = evidence.get("resource_type") or "unknown"
            resource_id = evidence.get("resource_id") or "unknown"
            timestamp = _normalize_timestamp(evidence.get("timestamp"))
            file_path = evidence.get("file_path") or "unknown"
            key = (resource_type, resource_id, timestamp, file_path)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "timestamp": timestamp,
                    "file_path": file_path,
                }
            )

    for risk in result.risks or []:
        add_evidence(_get_value(risk, "evidence", []))

    for item in result.missing_info or []:
        add_evidence(_get_value(item, "evidence", []))

    for item in result.contradictions or []:
        add_evidence(_get_value(item, "evidence", []))

    for entry in result.timeline or []:
        add_evidence(_get_value(entry, "evidence", []))

    citations.sort(
        key=lambda item: (
            item["resource_type"],
            item["resource_id"],
            item["timestamp"],
            item["file_path"],
        )
    )
    return citations


def _parse_date(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _dedupe_recent_problems(snapshot_text: str) -> list[str]:
    if not snapshot_text:
        return []

    lines = snapshot_text.splitlines()
    output: list[str] = []
    index = 0
    section_headers = {"Medications:", "Key vitals/labs:", "Risks:"}

    while index < len(lines):
        line = lines[index]
        if line.strip() != "Recent problems:":
            output.append(line)
            index += 1
            continue

        output.append(line)
        index += 1
        order: list[str] = []
        grouped: dict[str, tuple[Optional[datetime], str]] = {}
        while index < len(lines) and lines[index] not in section_headers:
            raw = lines[index].strip()
            index += 1
            if not raw:
                continue
            date_text, sep, label = raw.partition(" | ")
            if not sep:
                label = raw
                date_text = "unknown"
            label = label.strip() or "unknown"
            date_text = date_text.strip() or "unknown"
            date_value = _parse_date(date_text) if date_text != "unknown" else None
            if label not in grouped:
                grouped[label] = (date_value, date_text)
                order.append(label)
                continue
            current_date, current_text = grouped[label]
            if current_date is None and date_value is not None:
                grouped[label] = (date_value, date_text)
            elif current_date is not None and date_value is not None and date_value > current_date:
                grouped[label] = (date_value, date_text)
            elif current_date is None and date_value is None:
                grouped[label] = (current_date, current_text)

        for label in order:
            _, date_text = grouped[label]
            output.append(f"- {label} (most recent: {date_text})")

    return output


def _narrative_sentences(narrative: object) -> list[str]:
    parts: list[str] = []
    for key in ("summary_bullets", "risk_bullets", "followup_questions"):
        values = _get_value(narrative, key, []) or []
        for value in values:
            if not isinstance(value, str):
                continue
            text = value.strip()
            if text.startswith("-"):
                text = text.lstrip("-").strip()
            if text:
                parts.append(text)
    combined = " ".join(parts).strip()
    if not combined:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", combined)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def render_patient_report_md(result: PatientAnalysisResult) -> str:
    patient_id = result.meta.get("patient_id", "unknown")
    mode = result.meta.get("mode", "mock")

    risks = result.risks or []
    risks_sorted = sorted(
        risks,
        key=lambda risk: _severity_rank(_get_value(risk, "severity", None)),
        reverse=True,
    )

    lines: list[str] = [
        "# Patient Analysis Report",
        f"Patient ID: {patient_id}",
        f"Mode: {mode}",
        "",
        "## Snapshot",
    ]
    snapshot_lines = _dedupe_recent_problems(result.snapshot or "")
    if snapshot_lines:
        lines.extend(snapshot_lines)
    else:
        lines.append("")
    if risks:
        lines.append("")
        lines.append("Key risks:")
        for risk in risks_sorted:
            message = _get_value(risk, "message", "")
            lines.append(f"- {message}")
    lines.extend(
        [
            "",
            "## Top Risks",
            "| Severity | Rule | Message |",
            "| --- | --- | --- |",
        ]
    )
    for risk in risks_sorted:
        severity = _escape_table(_get_value(risk, "severity", "medium"))
        rule_id = _escape_table(_get_value(risk, "rule_id", "unknown"))
        message = _escape_table(_get_value(risk, "message", ""))
        lines.append(f"| {severity} | {rule_id} | {message} |")

    lines.append("")
    lines.append("## Timeline")
    timeline = result.timeline or []
    if timeline:
        for entry in timeline:
            date = _get_value(entry, "date", None) or "unknown"
            summary = _get_value(entry, "summary", None) or "unknown event"
            lines.append(f"- {date} — {summary}")
    else:
        lines.append("No structured timeline extracted from the available records.")

    lines.append("")
    lines.append("## Missing Information / Contradictions")
    missing_items = result.missing_info or []
    contradiction_items = result.contradictions or []
    if missing_items or contradiction_items:
        for item in missing_items:
            message = _get_value(item, "message", "")
            severity = _get_value(item, "severity", "unknown")
            lines.append(f"- Missing ({severity}): {message}")
        for item in contradiction_items:
            message = _get_value(item, "message", "")
            severity = _get_value(item, "severity", "unknown")
            lines.append(f"- Contradiction ({severity}): {message}")
    else:
        lines.append("No missing or contradictory information detected.")

    lines.append("")
    lines.append("## LLM Clinical Narrative (Excerpt)")
    if result.narrative:
        sentences = _narrative_sentences(result.narrative)
        if sentences:
            for sentence in sentences[:5]:
                lines.append(sentence)
            lines.append("(Full narrative available in artifact.)")
        else:
            lines.append("Narrative not generated (LLM unavailable or failed).")
    elif mode == "mock":
        lines.append("Narrative not generated (mock mode).")
    else:
        lines.append("Narrative not generated (LLM unavailable or failed).")

    lines.append("")
    lines.append("## Citations")
    lines.append("<details>")
    lines.append("<summary>Evidence & Citations</summary>")
    lines.append("")
    citations = _collect_citations(result)
    if citations:
        for citation in citations:
            lines.append(
                "- resource_type: {resource_type}; resource_id: {resource_id}; "
                "timestamp: {timestamp}; file_path: {file_path}".format(**citation)
            )
    else:
        lines.append("- No citations available.")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


__all__ = ["render_patient_report_md"]
