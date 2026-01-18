from __future__ import annotations

from typing import Iterable

KNOWN_TYPES = {
    "Patient",
    "Condition",
    "MedicationRequest",
    "MedicationStatement",
    "Medication",
    "Observation",
    "Encounter",
    "AllergyIntolerance",
}


def _flatten_resources(resources: list[dict]) -> Iterable[dict]:
    for item in resources:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if "payload" in item else item
        file_path = item.get("file_path")
        input_kind = item.get("input_kind")
        if not isinstance(payload, dict):
            continue
        resource_type = payload.get("resourceType")
        if resource_type == "Bundle":
            entries = payload.get("entry", [])
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        resource = entry.get("resource")
                        if isinstance(resource, dict):
                            yield {
                                "resource": resource,
                                "file_path": None if input_kind == "file" else file_path,
                                "input_kind": input_kind,
                                "bundle_file_path": file_path if input_kind == "file" else None,
                            }
        else:
            yield {"resource": payload, "file_path": file_path, "input_kind": input_kind}


def parse_fhir_resources(resources: list[dict]) -> dict[str, list[dict]]:
    """Group FHIR resources by resourceType, ignoring unknown types."""
    grouped: dict[str, list[dict]] = {}
    bundle_file_path = None
    for item in resources:
        if isinstance(item, dict) and item.get("input_kind") == "file":
            payload = item.get("payload")
            if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
                bundle_file_path = item.get("file_path")
                break
    for item in _flatten_resources(resources):
        resource = item.get("resource", item)
        if not isinstance(resource, dict):
            continue
        resource_type = resource.get("resourceType")
        if resource_type in KNOWN_TYPES:
            grouped.setdefault(resource_type, []).append(item)
    if bundle_file_path:
        grouped["__meta__"] = [{"bundle_file_path": bundle_file_path}]
    return grouped