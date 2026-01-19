from packages.ingest.synthea.normalizer import normalize_to_patient_chart


def test_medication_display_fallback_uses_rxnorm_code() -> None:
    grouped = {
        "MedicationRequest": [
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": "med-1",
                    "medicationCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                "code": "12345",
                            }
                        ]
                    },
                },
                "file_path": None,
            }
        ],
        "Patient": [{"resource": {"resourceType": "Patient", "id": "patient-1"}}],
    }
    chart = normalize_to_patient_chart(grouped)
    assert chart.medications[0].name == "RxNorm:12345"


def test_medication_display_fallback_uses_code_display() -> None:
    grouped = {
        "MedicationStatement": [
            {
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": "med-2",
                    "code": {
                        "coding": [
                            {
                                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                "code": "99999",
                                "display": "TestMed",
                            }
                        ]
                    },
                },
                "file_path": None,
            }
        ],
        "Patient": [{"resource": {"resourceType": "Patient", "id": "patient-2"}}],
    }
    chart = normalize_to_patient_chart(grouped)
    assert chart.medications[0].name == "TestMed"
