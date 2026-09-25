# TODO

## P0 Foundation
- [x] Scaffold FastAPI app
- [x] Scaffold Next.js app
- [x] Scaffold async worker
- [x] Add PostgreSQL + Redis Compose services
- [x] Add Alembic
- [x] Shared environment/config
- [x] CI lint/typecheck/test
- [x] Authentication/session foundation
- [x] AuditEvent model

## P0 Vertical slice
- [x] Document upload endpoint
- [x] Immutable storage service
- [x] SHA-256 dedupe
- [x] Native PDF extraction
- [x] OCR adapter
- [x] LM Studio adapter
- [x] Prescription extraction schema
- [x] Invoice extraction schema
- [x] HouseholdMember model
- [x] Family management UI
- [x] Patient resolver
- [x] MedicalEvent model
- [x] DocumentLink model
- [x] Deterministic link scoring
- [x] Insurance evaluation shell
- [x] Event graph API
- [x] Event graph UI
- [x] ReviewTask model/UI
- [x] Document detail UI (assigned patient and extracted fields)
- [x] Prescription-to-invoice E2E scenario with synthetic fixtures

## P1 Document platform
- [x] Watched directory
- [x] File-write stability detection
- [x] TIFF/HEIC
- [x] Thumbnails
- [x] OCR bbox persistence
- [x] Viewer highlights
- [x] Logical renaming
- [x] duplicate/re-scan detection

## P1 Pharmacy
- [x] Receipt schema / ReceiptLine
- [x] AIC OCR validation
- [x] AIFA importer + weekly sync
- [x] DrugPackage model
- [x] PrescriptionItem matcher
- [x] Mixed receipt allocation
- [x] patient-vs-payer review

## P1 Insurance
- [x] Review/activate 2026 rule set
- [x] Coverage-category engine
- [x] Required-document checklist
- [x] Diagnosis evidence policy
- [x] Physiotherapy grouping
- [x] Dental/preventive/lens rules
- [x] Hospital pre/post windows
- [x] Limits/franchise/coinsurance calculator
- [x] Insurance PDF/package export

## P1 Reimbursements
- [x] Reimbursement model
- [x] Manual/document import
- [x] Line-level allocation
- [x] Out-of-pocket reconciliation

## P1 Tax
- [x] TaxRuleSet
- [x] annual dependent status
- [x] PaymentEvidence
- [x] traceability checker
- [x] InsuranceTaxTreatment
- [x] tax allocation engine
- [x] year/member summary
- [x] CAF PDF/CSV/XLSX/ZIP

## P2 Pre-filled 730
- [x] Import
- [x] Normalize rows
- [x] Matching engine
- [x] Discrepancy UI

## P2 AI / Rizzo
- [x] Rizzo Flow adapter + batch typed decisions
- [x] fallback policy
- [x] prompt registry
- [x] AIExecution audit
- [x] embedding provider
- [x] calibration dataset
- [x] evaluate-rizzo command

## P2 Security / backup
- [ ] HTTPS LAN guide
- [ ] upload hardening
- [ ] auth rate limiting
- [ ] log-redaction tests
- [ ] encrypted local backup
- [ ] Google Drive encrypted upload
- [ ] restore verification
- [ ] key-management guide

## P3 Quality
- [ ] synthetic fixture generator
- [ ] E2E tests
- [ ] performance baseline
- [ ] disaster-recovery drill
- [ ] accessibility audit
- [ ] localization
