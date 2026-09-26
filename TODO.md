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
- [x] HTTPS LAN guide
- [x] upload hardening
- [x] auth rate limiting
- [x] log-redaction tests
- [x] encrypted local backup
- [x] Google Drive encrypted upload
- [x] restore verification
- [x] key-management guide
- [x] guarded local database reset
- [x] targeted document and household deletion

## P3 Quality
- [x] Strict chronological filtering for prescription/invoice links
- [x] Explain matching data and downstream destinations in link reviews
- [x] Open logical-name graph nodes in the document viewer
- [x] Explain documented expense and reimbursement estimate separately
- [x] Manual completion for unclassified document reviews
- [x] Contextual draggable document viewer
- [x] Full LLM relationship rebuild, duplicate prevention, and approved archive
- [x] Manual start for pending local document analysis
- [x] Recovery action for stalled local document analysis
- [x] Large-model fallback extraction and guarded relationship matching
- [x] Runtime LLM routing and safe job pause controls
- [x] Dedicated settings tab with runtime configuration feedback
- [x] CORS preflight support for runtime settings updates
- [x] Automatic normalization of local model bounding-box coordinates
- [x] Actionable review queue and orphaned-review cleanup
- [x] Responsive visual design system
- [x] Extracted clinical-data side panel in document viewer
- [x] Specialty-safe clinical relation matching and serialized local processing
- [x] Two-request local model concurrency limit
- [x] Thirty-minute local model request timeout
- [x] Small-model structured extraction with itemized drug and lab-test matching
- [x] Generic structured fallback for documents requiring review
- [x] Per-document forced local reanalysis action
- [x] Aligned per-document analysis and deletion actions
- [x] Deterministic laboratory-test and medicine item normalization
- [x] Structured laboratory-result report recognition
- [x] Explicit prescribed-medicine viewer summary
- [x] Documented specialist-visit service extraction
- [x] Overflow-safe Inbox document filenames
- [x] Semantic Inbox pipeline-state colors
- [x] Live analysis polling and phase timebars
- [ ] synthetic fixture generator
- [ ] E2E tests
- [ ] performance baseline
- [ ] disaster-recovery drill
- [ ] accessibility audit
- [ ] localization
