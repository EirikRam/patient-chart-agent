from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from packages.core.schemas.output import NarrativeSummary


class PatientAnalysisResult(BaseModel):
    snapshot: Optional[str] = None
    risks: List[dict] = Field(default_factory=list)
    narrative: Optional[NarrativeSummary] = None
    meta: Dict[str, str] = Field(default_factory=dict)


__all__ = ["PatientAnalysisResult"]
