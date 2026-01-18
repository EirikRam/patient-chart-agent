from __future__ import annotations

from packages.core.schemas.chart import PatientChart

RULE_ID = "followup_missing"
SEVERITY = "medium"


def run(chart: PatientChart) -> list[dict]:
    _ = chart
    return []