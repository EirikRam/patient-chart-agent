from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from packages.core.schemas.chart import (
    Allergy,
    Condition,
    Encounter,
    Medication,
    Note,
    Observation,
    PatientChart,
    SourceRef,
)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_item(items: Any) -> Optional[dict]:
    if isinstance(items, list) and items:
        item = items[0]
        return item if isinstance(item, dict) else None
    return None


def _resource_with_path(item: Any) -> tuple[dict, Optional[str]]:
    if not isinstance(item, dict):
        return {}, None
    resource = item.get("resource", item)
    file_path = item.get("file_path")
    return resource if isinstance(resource, dict) else {}, file_path


def _code_display(codeable: Any) -> tuple[Optional[str], Optional[str]]:
    if not isinstance(codeable, dict):
        return None, None
    coding = _first_item(codeable.get("coding"))
    code = coding.get("code") if coding else None
    display = coding.get("display") if coding else None
    text = codeable.get("text")
    return code or text, display or text


def _select_coding(codeable: Any, prefer: str) -> Optional[dict]:
    if not isinstance(codeable, dict):
        return None
    codings = codeable.get("coding")
    if not isinstance(codings, list):
        return None
    prefer_lower = prefer.lower()
    for coding in codings:
        system = coding.get("system")
        if isinstance(system, str) and prefer_lower in system.lower():
            return coding
    return _first_item(codings)


def _string_value(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _float_value(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_ref(resource: dict, file_path: Optional[str]) -> SourceRef:
    resource_type = _string_value(resource.get("resourceType"))
    resource_id = _string_value(resource.get("id"))
    doc_id = None
    if resource_type and resource_id:
        doc_id = f"{resource_type}/{resource_id}"
    timestamp = None
    meta = resource.get("meta")
    if isinstance(meta, dict):
        timestamp = _parse_datetime(_string_value(meta.get("lastUpdated")))
    return SourceRef(
        doc_id=doc_id or "",
        resource_type=resource_type,
        resource_id=resource_id,
        file_path=file_path,
        timestamp=timestamp,
    )


def normalize_to_patient_chart(grouped: dict[str, list[dict]]) -> PatientChart:
    """Normalize grouped FHIR resources into a minimal PatientChart."""
    meta_items = grouped.get("__meta__", [])
    meta = meta_items[0] if meta_items and isinstance(meta_items[0], dict) else {}
    bundle_file_path = meta.get("bundle_file_path")
    patient_item = _first_item(grouped.get("Patient", [])) or {}
    patient, patient_file = _resource_with_path(patient_item)
    patient_id = _string_value(patient.get("id")) or "unknown"

    demographics: dict[str, Any] = {}
    name = _first_item(patient.get("name"))
    if name:
        given = name.get("given") or []
        if isinstance(given, list):
            given_str = " ".join([part for part in given if isinstance(part, str)])
        else:
            given_str = ""
        family = _string_value(name.get("family")) or ""
        full_name = " ".join([part for part in [given_str, family] if part]).strip()
        if full_name:
            demographics["name"] = full_name
    gender = _string_value(patient.get("gender"))
    if gender:
        demographics["gender"] = gender
    birth_date = _string_value(patient.get("birthDate"))
    if birth_date:
        demographics["birth_date"] = birth_date

    conditions = []
    for item in grouped.get("Condition", []):
        resource, file_path = _resource_with_path(item)
        code, display = _code_display(resource.get("code"))
        clinical_status = _code_display(resource.get("clinicalStatus"))[0]
        conditions.append(
            Condition(
                id=_string_value(resource.get("id")) or "",
                code=code,
                display=display,
                onset=_parse_datetime(resource.get("onsetDateTime")),
                abatement=_parse_datetime(resource.get("abatementDateTime")),
                clinical_status=clinical_status,
                sources=[_source_ref(resource, file_path)],
            )
        )

    medications = []
    for item in grouped.get("MedicationRequest", []):
        resource, file_path = _resource_with_path(item)
        code, display = _code_display(resource.get("medicationCodeableConcept"))
        dosage = _first_item(resource.get("dosageInstruction")) or {}
        medications.append(
            Medication(
                id=_string_value(resource.get("id")) or "",
                name=display or code,
                status=_string_value(resource.get("status")),
                authored_on=_parse_datetime(resource.get("authoredOn")),
                dosage_text=_string_value(dosage.get("text")),
                sources=[_source_ref(resource, file_path)],
            )
        )
    for item in grouped.get("MedicationStatement", []):
        resource, file_path = _resource_with_path(item)
        code, display = _code_display(resource.get("medicationCodeableConcept"))
        dosage = _first_item(resource.get("dosage")) or {}
        medications.append(
            Medication(
                id=_string_value(resource.get("id")) or "",
                name=display or code,
                status=_string_value(resource.get("status")),
                authored_on=_parse_datetime(resource.get("effectiveDateTime")),
                dosage_text=_string_value(dosage.get("text")),
                sources=[_source_ref(resource, file_path)],
            )
        )

    observations = []
    for item in grouped.get("Observation", []):
        resource, file_path = _resource_with_path(item)
        codeable = resource.get("code")
        coding = _select_coding(codeable, "loinc")
        code, display = _code_display(codeable)
        value_qty = resource.get("valueQuantity") or {}
        code_system = None
        if isinstance(coding, dict):
            code_system = _string_value(coding.get("system"))
        category = None
        category_concept = _first_item(resource.get("category"))
        if category_concept:
            category_coding = _first_item(category_concept.get("coding"))
            if category_coding:
                category = category_coding.get("code") or category_coding.get("display")
            if not category:
                category = _string_value(category_concept.get("text"))
        effective_dt = _parse_datetime(resource.get("effectiveDateTime"))
        components = []
        for component in resource.get("component", []) or []:
            if not isinstance(component, dict):
                continue
            comp_codeable = component.get("code")
            comp_coding = _select_coding(comp_codeable, "loinc")
            comp_code, comp_display = _code_display(comp_codeable)
            comp_value = component.get("valueQuantity") or {}
            comp_code_system = None
            if isinstance(comp_coding, dict):
                comp_code_system = _string_value(comp_coding.get("system"))
            components.append(
                {
                    "code": comp_code,
                    "code_system": comp_code_system,
                    "display": comp_display,
                    "value": _float_value(comp_value.get("value")),
                    "unit": _string_value(comp_value.get("unit")),
                }
            )

        observations.append(
            Observation(
                id=_string_value(resource.get("id")) or "",
                code=code,
                code_system=code_system,
                display=display,
                value=_float_value(value_qty.get("value")),
                value_text=_string_value(resource.get("valueString")),
                unit=_string_value(value_qty.get("unit")),
                effective=effective_dt,
                effective_dt=effective_dt,
                category=_string_value(category),
                components=components,
                sources=[_source_ref(resource, file_path)],
            )
        )

    encounters = []
    for item in grouped.get("Encounter", []):
        resource, file_path = _resource_with_path(item)
        encounter_type = _first_item(resource.get("type"))
        type_code, type_display = _code_display(encounter_type or {})
        reason = _first_item(resource.get("reasonCode"))
        reason_code, reason_display = _code_display(reason or {})
        period = resource.get("period") or {}
        encounters.append(
            Encounter(
                id=_string_value(resource.get("id")) or "",
                start=_parse_datetime(period.get("start")),
                end=_parse_datetime(period.get("end")),
                type=type_display or type_code,
                reason=reason_display or reason_code,
                sources=[_source_ref(resource, file_path)],
            )
        )

    allergies = []
    for item in grouped.get("AllergyIntolerance", []):
        resource, file_path = _resource_with_path(item)
        code, display = _code_display(resource.get("code"))
        reaction = _first_item(resource.get("reaction")) or {}
        manifestation = _first_item(reaction.get("manifestation")) or {}
        reaction_text = _string_value(manifestation.get("text"))
        if not reaction_text:
            _, reaction_text = _code_display(manifestation)
        allergies.append(
            Allergy(
                id=_string_value(resource.get("id")) or "",
                substance=display or code,
                criticality=_string_value(resource.get("criticality")),
                reaction=reaction_text,
                recorded_date=_parse_datetime(resource.get("recordedDate")),
                sources=[_source_ref(resource, file_path)],
            )
        )

    sources = [_source_ref(patient, patient_file)]
    if bundle_file_path:
        sources.append(SourceRef(doc_id="bundle", file_path=bundle_file_path))

    return PatientChart(
        patient_id=patient_id,
        demographics=demographics,
        encounters=encounters,
        conditions=conditions,
        medications=medications,
        allergies=allergies,
        observations=observations,
        notes=[],
        sources=sources,
    )