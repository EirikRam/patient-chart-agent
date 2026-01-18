from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Pointer back to the original data source for citation/audit."""
    doc_id: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    file_path: Optional[str] = None
    timestamp: Optional[datetime] = None


class Encounter(BaseModel):
    id: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    type: Optional[str] = None
    reason: Optional[str] = None
    sources: List[SourceRef] = Field(default_factory=list)


class Condition(BaseModel):
    id: str
    code: Optional[str] = None
    display: Optional[str] = None
    onset: Optional[datetime] = None
    abatement: Optional[datetime] = None
    clinical_status: Optional[str] = None
    sources: List[SourceRef] = Field(default_factory=list)


class Medication(BaseModel):
    id: str
    name: Optional[str] = None
    status: Optional[str] = None
    authored_on: Optional[datetime] = None
    dosage_text: Optional[str] = None
    sources: List[SourceRef] = Field(default_factory=list)


class Allergy(BaseModel):
    id: str
    substance: Optional[str] = None
    criticality: Optional[str] = None
    reaction: Optional[str] = None
    recorded_date: Optional[datetime] = None
    sources: List[SourceRef] = Field(default_factory=list)


class Observation(BaseModel):
    """Labs or vitals."""
    id: str
    code: Optional[str] = None
    display: Optional[str] = None
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    effective: Optional[datetime] = None
    category: Optional[str] = None  # "lab" or "vital" (or None)
    sources: List[SourceRef] = Field(default_factory=list)


class Note(BaseModel):
    id: str
    authored: Optional[datetime] = None
    type: Optional[str] = None
    text: str = ""
    sources: List[SourceRef] = Field(default_factory=list)


class PatientChart(BaseModel):
    """Canonical, model-friendly view of a patient's chart."""
    patient_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    demographics: Dict[str, Any] = Field(default_factory=dict)

    encounters: List[Encounter] = Field(default_factory=list)
    conditions: List[Condition] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)
    allergies: List[Allergy] = Field(default_factory=list)

    observations: List[Observation] = Field(default_factory=list)
    notes: List[Note] = Field(default_factory=list)

    # raw source pointers for audit/debug
    sources: List[SourceRef] = Field(default_factory=list)


__all__ = [
    "SourceRef",
    "Encounter",
    "Condition",
    "Medication",
    "Allergy",
    "Observation",
    "Note",
    "PatientChart",
]