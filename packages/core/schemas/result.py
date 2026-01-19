from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from packages.core.schemas.chart import SourceRef
from packages.core.schemas.output import NarrativeSummary


Evidence = SourceRef


class TimelineEntry(BaseModel):
    date: str
    type: str
    summary: str
    evidence: List[Evidence] = Field(default_factory=list)


class MissingInfoItem(BaseModel):
    id: str
    severity: str
    message: str
    evidence: List[Evidence] = Field(default_factory=list)


class ContradictionItem(BaseModel):
    id: str
    severity: str
    message: str
    evidence: List[Evidence] = Field(default_factory=list)


class PatientAnalysisResult(BaseModel):
    snapshot: Optional[str] = None
    risks: List[dict] = Field(default_factory=list)
    narrative: Optional[NarrativeSummary] = None
    meta: Dict[str, str] = Field(default_factory=dict)
    timeline: Optional[List[TimelineEntry]] = None
    missing_info: Optional[List[MissingInfoItem]] = None
    contradictions: Optional[List[ContradictionItem]] = None


__all__ = [
    "Evidence",
    "TimelineEntry",
    "MissingInfoItem",
    "ContradictionItem",
    "PatientAnalysisResult",
]
