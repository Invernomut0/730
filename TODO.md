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
- [ ] Review/activate 2026 rule set
- [ ] Coverage-category engine
- [ ] Required-document checklist
- [ ] Diagnosis evidence policy
- [ ] Physiotherapy grouping
- [ ] Dental/preventive/lens rules
- [ ] Hospital pre/post windows
- [ ] Limits/franchise/coinsurance calculator
- [ ] Insurance PDF/package export

## P1 Reimbursements
- [ ] Reimbursement model
- [ ] Manual/document import
- [ ] Line-level allocation
- [ ] Out-of-pocket reconciliation

## P1 Tax
- [ ] TaxRuleSet
- [ ] annual dependent status
- [ ] PaymentEvidence
- [ ] traceability checker
- [ ] InsuranceTaxTreatment
- [ ] tax allocation engine
- [ ] year/member summary
- [ ] CAF PDF/CSV/XLSX/ZIP

## P2 Pre-filled 730
- [ ] Import
- [ ] Normalize rows
- [ ] Matching engine
- [ ] Discrepancy UI

## P2 AI / Rizzo
- [ ] Rizzo Flow adapter + batch typed decisions
- [ ] fallback policy
- [ ] prompt registry
- [ ] AIExecution audit
- [ ] embedding provider
- [ ] calibration dataset
- [ ] evaluate-rizzo command

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
