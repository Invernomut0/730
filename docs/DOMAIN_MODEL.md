# Domain Model

## Core entities
**Household**: family unit.

**HouseholdMember**: name, fiscal code, birth date, relationship, insurance coverage periods, dependent status per tax year.

**Document**: immutable file; sha256, MIME, original/logical filename, storage key, import time, processing state.

**DocumentPage**: page text, OCR blocks, bounding boxes.

**ExpenseDocument**: invoice/receipt/ticket abstraction.

**ExpenseLine**: atomic monetary item. Mandatory for mixed receipts and partial allocations.

**Prescription / PrescriptionItem**: patient, doctor, date, diagnosis evidence, requested service/drug, dosage, source spans.

**MedicalReport**: report type, findings, conclusions, diagnosis evidence.

**DiagnosisEvidence** types: CONFIRMED_DIAGNOSIS, SUSPECTED_DIAGNOSIS, DIAGNOSTIC_QUESTION, CLINICAL_INDICATION, SYMPTOM, ANAMNESIS, REPORT_CONCLUSION.

**MedicalEvent**: central cluster representing one disease/injury/care cycle.

**DocumentLink**: relation with score, evidence, conflicts, source and manual override.

**InsuranceClaim / InsuranceClaimItem**: claim and allocated expenses for one MedicalEvent.

**InsuranceReimbursement**: claimed, accepted, rejected, reimbursed, deductible and coinsurance amounts.

**TaxAllocation**: tax-year allocation to a tax subject with reimbursement and traceability context.

**PaymentEvidence**: POS receipt, bank transfer, statement, PagoPA or invoice annotation.

**Drug / DrugPackage**: local AIFA catalog entities keyed by AIC.

**ReviewTask**: unresolved ambiguity.

**AIExecution / RuleExecution / UserCorrection / AuditEvent**: provenance, explainability and calibration.
