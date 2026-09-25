# Implementation Plan

## M0 Foundation
FastAPI/Next.js/worker skeletons, PostgreSQL, Redis, Docker, Alembic, auth foundation, CI, lint/test.

## M1 Vertical slice
Prescription + invoice upload -> extraction -> LM Studio structured data -> household identification -> MedicalEvent -> insurance candidate -> graph UI.

**Exit:** real data end-to-end; no fake feature cards.

## M2 Document platform
Watched folder, dedupe, thumbnailing, document viewer, OCR/bboxes, logical rename/reprocess.

## M3 Family identity
Household CRUD, coverage periods, tax-dependent status, patient/payer/tax-subject separation and conflict review.

## M4 Pharmacy
Receipt-line extraction, AIC validation, local AIFA catalog, medicine-prescription matching, mixed receipts.

## M5 Insurance 2026
Executable rules, completeness checklists, limits/franchises/coinsurance estimates, claim export.

## M6 Reimbursements
Import/manual entry, line allocation, actual-vs-estimated reconciliation.

## M7 Tax engine
Versioned annual rules, traceability evidence, taxpayer allocation and residual amounts.

## M8 Pre-filled 730
Import, normalization, local-vs-prefilled matching and discrepancy UI.

## M9 Feedback/calibration
Persist corrections, Rizzo evaluation dataset, calibration, model/prompt comparisons.

## M10 Backup/hardening
Encrypted Google Drive backup/restore, HTTPS LAN deployment, audit review, performance and disaster recovery.

## Delivery policy
Every milestone includes migrations, tests, docs and observability.
