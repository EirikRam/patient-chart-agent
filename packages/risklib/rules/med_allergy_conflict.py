from __future__ import annotations

from packages.core.schemas.chart import PatientChart

RULE_ID = "med_allergy_conflict"
SEVERITY = "medium"


def run(chart: PatientChart) -> list[dict]:
    _ = chart
    return []