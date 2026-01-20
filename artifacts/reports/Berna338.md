# Patient Analysis Report
Patient ID: 0c1a1859-29c7-4f11-f21c-20a7099e8613
Mode: mock

## Snapshot
Patient: 0c1a1859-29c7-4f11-f21c-20a7099e8613 | sex=female | age=28 | last_seen=2025-12-01
Recent problems:
2025-12-01 | Medication review due (situation)
2025-12-01 | Medication review due (situation)
2025-11-29 | Medication review due (situation)
2025-11-29 | Medication review due (situation)
2025-11-27 | Medication review due (situation)
Medications:
2025-12-01 | Hydrochlorothiazide 25 MG Oral Tablet
2025-12-01 | 24 HR tacrolimus 1 MG Extended Release Oral Tablet [Envarsus]
2025-12-01 | amLODIPine 2.5 MG Oral Tablet
2025-11-27 | insulin isophane, human 70 UNT/ML / insulin, regular, human 30 UNT/ML Injectable Suspension [Humulin]
2025-11-27 | lisinopril 10 MG Oral Tablet
2025-11-27 | Acetaminophen 300 MG / Hydrocodone Bitartrate 5 MG Oral Tablet
2025-11-26 | Unknown medication
2025-11-26 | Unknown medication
Key vitals/labs:
BP (85354-9): 122/92 on 2025-12-01 | src: Observation/fb62c08e-8900-5fb2-ac0c-6cd416a0be90
BMI (39156-5): 32.21 kg/m2 on 2025-12-01 | src: Observation/fb62c08e-8900-5fb2-23d1-b59256a4f06f
A1c (4548-4): 5.96 % on 2025-11-29 | src: Observation/45dff467-def6-2132-28ab-3d6da2bec3ed
Creatinine (2160-0): 2.0556 mg/dL on 2025-12-01 | src: Observation/fb62c08e-8900-5fb2-7033-8488ec5da2ad
Potassium (6298-4): 4.86 mmol/L on 2025-11-29 | src: Observation/45dff467-def6-2132-6854-44a9875bfade
Risks:
lab_a1c_elevated | medium | A1c in prediabetes range: 5.96 % on 2025-11-29
  - src: Observation/45dff467-def6-2132-28ab-3d6da2bec3ed
vitals_bmi_obesity | medium | BMI in obesity range: 32.21 on 2025-12-01
  - src: Observation/fb62c08e-8900-5fb2-23d1-b59256a4f06f
vitals_bp_elevated | medium | elevated BP: 122/92 on 2025-12-01
  - src: Observation/fb62c08e-8900-5fb2-ac0c-6cd416a0be90

## Top Risks
| Severity | Rule | Message |
| --- | --- | --- |
| medium | lab_a1c_elevated | A1c in prediabetes range: 5.96 % on 2025-11-29 |
| medium | vitals_bmi_obesity | BMI in obesity range: 32.21 on 2025-12-01 |
| medium | vitals_bp_elevated | elevated BP: 122/92 on 2025-12-01 |

## Timeline
No structured timeline available.

## Missing Information / Contradictions
No missing or contradictory information detected.

## LLM Clinical Narrative (Excerpt)
Narrative not generated.

## Citations
<details>
<summary>Evidence & Citations</summary>

- resource_type: Observation; resource_id: 45dff467-def6-2132-28ab-3d6da2bec3ed; timestamp: 2025-11-29T07:21:42+00:00; file_path: data\raw\fhir_ehr_synthea\samples_100
- resource_type: Observation; resource_id: fb62c08e-8900-5fb2-23d1-b59256a4f06f; timestamp: 2025-12-01T12:17:21+00:00; file_path: data\raw\fhir_ehr_synthea\samples_100
- resource_type: Observation; resource_id: fb62c08e-8900-5fb2-ac0c-6cd416a0be90; timestamp: 2025-12-01T12:17:21+00:00; file_path: data\raw\fhir_ehr_synthea\samples_100

</details>
