# TODO

## P0 Foundation
- [ ] Scaffold FastAPI app
- [ ] Scaffold Next.js app
- [ ] Scaffold async worker
- [ ] Add PostgreSQL + Redis Compose services
- [ ] Add Alembic
- [ ] Shared environment/config
- [ ] CI lint/typecheck/test
- [ ] Authentication/session foundation
- [ ] AuditEvent model

## P0 Vertical slice
- [ ] Document upload endpoint
- [ ] Immutable storage service
- [ ] SHA-256 dedupe
- [ ] Native PDF extraction
- [ ] OCR adapter
- [ ] LM Studio adapter
- [ ] Prescription extraction schema
- [ ] Invoice extraction schema
- [ ] HouseholdMember model
- [ ] Patient resolver
- [ ] MedicalEvent model
- [ ] DocumentLink model
- [ ] Deterministic link scoring
- [ ] Insurance evaluation shell
- [ ] Event graph API
- [ ] Event graph UI
- [ ] ReviewTask model/UI

## P1 Document platform
- [ ] Watched directory
- [ ] File-write stability detection
- [ ] TIFF/HEIC
- [ ] Thumbnails
- [ ] OCR bbox persistence
- [ ] Viewer highlights
- [ ] Logical renaming
- [ ] duplicate/re-scan detection

## P1 Pharmacy
- [ ] Receipt schema / ReceiptLine
- [ ] AIC OCR validation
- [ ] AIFA importer + weekly sync
- [ ] DrugPackage model
- [ ] PrescriptionItem matcher
- [ ] Mixed receipt allocation
- [ ] patient-vs-payer review

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
