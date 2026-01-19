from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from packages.core.schemas.chart import Observation, PatientChart
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.steps.risks import run_risk_rules
from packages.pipeline.steps.timeline import build_timeline

LOINC_SYSTEM = "http://loinc.org"


def _format_date(value: Optional[datetime]) -> str:
    return value.date().isoformat() if value else "unknown"


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _years_between(earlier: date, later: date) -> int:
    years = later.year - earlier.year
    if (later.month, later.day) < (earlier.month, earlier.day):
        years -= 1
    return years


def _obs_date(obs: Observation) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def get_most_recent_observation(
    chart: PatientChart, loinc_code: str
) -> tuple[Optional[float], Optional[str], Optional[datetime], Optional[str]]:
    candidates = []
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code != loinc_code:
            continue
        date_value = _obs_date(obs)
        if not date_value:
            continue
        candidates.append((date_value, obs))
    if not candidates:
        return None, None, None, None
    candidates.sort(key=lambda item: item[0])
    date_value, obs = candidates[-1]
    return obs.value, obs.unit, date_value, obs.id


def get_most_recent_bp(
    chart: PatientChart,
) -> tuple[Optional[float], Optional[float], Optional[datetime], Optional[str]]:
    candidates = []
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code != "85354-9":
            continue
        date_value = _obs_date(obs)
        if not date_value:
            continue
        systolic = None
        diastolic = None
        for component in obs.components:
            if component.get("code_system") != LOINC_SYSTEM:
                continue
            if component.get("code") == "8480-6":
                systolic = component.get("value")
            if component.get("code") == "8462-4":
                diastolic = component.get("value")
        if systolic is None or diastolic is None:
            continue
        candidates.append((date_value, float(systolic), float(diastolic), obs.id))
    if not candidates:
        return None, None, None, None
    candidates.sort(key=lambda item: item[0])
    date_value, systolic, diastolic, obs_id = candidates[-1]
    return systolic, diastolic, date_value, obs_id


def build_snapshot_from_chart(chart: PatientChart) -> str:
    timeline = build_timeline(chart)
    risks = run_risk_rules(chart)

    last_seen = timeline[-1]["date"] if timeline else None
    birth_date = _parse_date(chart.demographics.get("birth_date"))
    age_text = ""
    if birth_date and last_seen:
        age_text = str(_years_between(birth_date, last_seen.date()))
    sex = chart.demographics.get("gender", "unknown")

    lines = []
    patient_line = (
        f"Patient: {chart.patient_id} | sex={sex} | "
        f"age={age_text or 'unknown'} | last_seen={_format_date(last_seen)}"
    )
    lines.append(patient_line)

    conditions = []
    for condition in chart.conditions:
        date_value = condition.onset or condition.abatement
        if not date_value:
            continue
        label = condition.display or condition.code or "condition"
        conditions.append((date_value, label))
    conditions.sort(key=lambda item: item[0], reverse=True)
    lines.append("Recent problems:")
    for date_value, label in conditions[:5]:
        lines.append(f"{_format_date(date_value)} | {label}")

    medications = []
    for med in chart.medications:
        if not med.authored_on:
            continue
        label = med.name or "medication"
        medications.append((med.authored_on, label))
    medications.sort(key=lambda item: item[0], reverse=True)
    lines.append("Medications:")
    for date_value, label in medications[:8]:
        lines.append(f"{_format_date(date_value)} | {label}")

    lines.append("Key vitals/labs:")
    systolic, diastolic, bp_date, bp_id = get_most_recent_bp(chart)
    if systolic is not None and diastolic is not None and bp_date and bp_id:
        lines.append(
            f"BP (85354-9): {systolic:.0f}/{diastolic:.0f} on {_format_date(bp_date)} | src: Observation/{bp_id}"
        )
    for code, label in [
        ("39156-5", "BMI"),
        ("4548-4", "A1c"),
        ("2160-0", "Creatinine"),
        ("6298-4", "Potassium"),
    ]:
        value, unit, date_value, obs_id = get_most_recent_observation(chart, code)
        if value is None or not date_value or not obs_id:
            continue
        unit_text = f" {unit}" if unit else ""
        lines.append(
            f"{label} ({code}): {value}{unit_text} on {_format_date(date_value)} | src: Observation/{obs_id}"
        )

    lines.append("Risks:")
    for risk in risks:
        rule_id = risk.get("rule_id", "unknown")
        severity = risk.get("severity", "medium")
        message = risk.get("message", "")
        lines.append(f"{rule_id} | {severity} | {message}")
        evidence = risk.get("evidence") or []
        for source in evidence:
            resource_type = getattr(source, "resource_type", None) or "unknown"
            resource_id = getattr(source, "resource_id", None) or "unknown"
            lines.append(f"  - src: {resource_type}/{resource_id}")

    return "\n".join(lines)


def build_snapshot(patient_json_path: str) -> str:
    path = Path(patient_json_path)
    resources = load_patient_dir(path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)
    return build_snapshot_from_chart(chart)


__all__ = ["build_snapshot", "build_snapshot_from_chart"]
