from __future__ import annotations

from packages.core.schemas.chart import PatientChart

RULE_ID = "duplicate_therapy"
SEVERITY = "medium"


def run(chart: PatientChart) -> list[dict]:
    _ = chart
    return []