# Document Linking and Medical Event Clustering

## Goal
Infer relationships while prioritizing precision over recall.

## Strong signals
Exact patient identity, prescription/invoice reference, AIC/drug match, provider, explicit service and diagnosis/question match.

## Supporting signals
Temporal proximity, specialty, provider, treatment sequence and semantic similarity.

## Conflicts
Explicit different patient, impossible chronology, incompatible medicine/prescription or contradictory event.

## Temporal policy
Default previous-report/diagnosis lookback: 365 days. Category-specific rules may override. Time is evidence, not proof.

## Initial scoring example
- exact drug/AIC +0.35
- clinical patient match +0.30
- compatible date +0.15
- diagnosis/event compatibility +0.15
- semantic similarity +0.05
- explicit different patient -1.00

Weights are versioned configuration.

## Thresholds
Auto-confirm >= 0.95 with no major conflict; suggest >= 0.75; otherwise review.

## Relations
BELONGS_TO_PATIENT, PAID_BY, PRESCRIBES, DIAGNOSES, REPORTS, BILLS, PURCHASES, MEDICATION_FOR, PAYMENT_FOR, PART_OF_EVENT, SUBMITTED_IN, REIMBURSES, TAX_ALLOCATED_TO, RELATED_TO.
