from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class NarrativeSummary(BaseModel):
    patient_id: str
    summary_bullets: List[str] = Field(default_factory=list)
    risk_bullets: List[str] = Field(default_factory=list)
    followup_questions: List[str] = Field(default_factory=list)
    citations: Dict[str, List[str]] = Field(default_factory=dict)


__all__ = ["NarrativeSummary"]