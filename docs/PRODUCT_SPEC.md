# Product Specification

## Scope
HealthDocs manages health documents for multiple household members across multiple years, insurance plan versions and tax years.

## Inputs
PDF, JPG, JPEG, PNG, TIFF and HEIC from web upload or a watched folder.

## Document taxonomy
INVOICE, PRESCRIPTION, MEDICAL_REPORT, PHARMACY_RECEIPT, PAYMENT_PROOF, HOSPITAL_RECORD, DENTAL_PLAN, OPTICAL_PRESCRIPTION, INSURANCE_REIMBURSEMENT, TAX_PRECOMPILED_DOCUMENT, OTHER, UNKNOWN.

## Capabilities
1. ingest and deduplicate;
2. native extraction and OCR;
3. classify documents;
4. extract structured fields;
5. identify household member(s);
6. split expense documents into atomic lines;
7. resolve medicines by AIC;
8. link related records;
9. cluster records into MedicalEvent;
10. evaluate insurance eligibility/completeness;
11. record actual reimbursements;
12. evaluate 730 allocation;
13. reconcile with pre-filled 730;
14. export insurance and CAF-ready packages;
15. learn from user corrections.

## Critical domain rules
- patient, payer, insured member, tax subject and fiscal-code holder are separate concepts;
- one document may contribute to several logical practices;
- one pharmacy receipt may contain products for multiple family members;
- clinical evidence can override receipt fiscal-code ownership for patient attribution;
- false-positive linking is worse than a review request;
- every material AI decision exposes evidence and conflicts;
- insurance/tax rules live in versioned rule sets, never only in prompts.

## UX
Desktop-first, graph-centric workspace combining preview, timeline, graph, extracted metadata, evidence/conflicts and review actions.

## Non-goals for MVP
No SPID/CIE credential storage, authenticated OneCare scraping, automatic claim submission, automatic tax filing or autonomous fine-tuning.
