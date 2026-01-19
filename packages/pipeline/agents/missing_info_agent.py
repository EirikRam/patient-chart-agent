from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from packages.core.schemas.chart import PatientChart
from packages.core.schemas.result import MissingInfoItem

LOINC_SYSTEM = "http://loinc.org"
A1C_CODES = {"4548-4"}
BP_PANEL_CODE = "85354-9"


def _obs_date(obs) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def _reference_date(chart: PatientChart) -> Optional[datetime]:
    dates = []
    for obs in chart.observations:
        date_value = _obs_date(obs)
        if date_value:
            dates.append(date_value)
    for encounter in chart.encounters:
        date_value = encounter.start or encounter.end
        if date_value:
            dates.append(date_value)
    if not dates:
        return None
    return max(dates)


def _has_condition_match(chart: PatientChart, tokens: tuple[str, ...]) -> bool:
    for condition in chart.conditions:
        text = " ".join([condition.display or "", condition.code or ""]).lower()
        if any(token in text for token in tokens):
            return True
    return False


def _most_recent_a1c_date(chart: PatientChart) -> Optional[datetime]:
    candidates = []
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code not in A1C_CODES:
            continue
        date_value = _obs_date(obs)
        if date_value:
            candidates.append(date_value)
    return max(candidates) if candidates else None


def _most_recent_bp_date(chart: PatientChart) -> Optional[datetime]:
    candidates = []
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code != BP_PANEL_CODE:
            continue
        date_value = _obs_date(obs)
        if date_value:
            candidates.append(date_value)
    return max(candidates) if candidates else None


def run_missing_info_agent(chart: PatientChart) -> list[MissingInfoItem]:
    """Return deterministic missing-info items based on chart content."""
    missing: list[MissingInfoItem] = []
    reference_date = _reference_date(chart)
    if not reference_date:
        return missing

    diabetes_present = _has_condition_match(chart, ("diabetes",))
    hypertension_present = _has_condition_match(chart, ("hypertension", "high blood pressure", "htn"))

    if diabetes_present:
        recent_a1c = _most_recent_a1c_date(chart)
        if not recent_a1c or recent_a1c < reference_date - timedelta(days=365):
            missing.append(
                MissingInfoItem(
                    id="missing_hba1c_recent",
                    severity="medium",
                    message=(
                        "Diabetes is documented in the record, but no HbA1c observation "
                        "was found within the past 12 months."
                    ),
                    evidence=[],
                )
            )

    if hypertension_present:
        recent_bp = _most_recent_bp_date(chart)
        if not recent_bp or recent_bp < reference_date - timedelta(days=180):
            missing.append(
                MissingInfoItem(
                    id="missing_bp_recent",
                    severity="low",
                    message=(
                        "Hypertension is documented in the record, but no blood pressure "
                        "measurements were found within the past 6 months."
                    ),
                    evidence=[],
                )
            )

    return missing


__all__ = ["run_missing_info_agent"]
