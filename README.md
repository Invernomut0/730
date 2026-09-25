# HealthDocs 730

Local-first web application for managing multi-year household health documents, insurance claims and Italian 730 tax preparation.

## Product goals
- ingest PDF/images from web upload or watched folder;
- classify invoices, prescriptions, reports, receipts and supporting evidence;
- build explainable `MedicalEvent` graphs;
- prepare insurance claims according to versioned plan rules;
- track reimbursements and residual out-of-pocket expenses;
- reconcile local expenses with the Italian pre-filled 730;
- keep medical data local; external services receive only non-personal identifiers such as AIC codes;
- support encrypted backup to Google Drive.

## Monorepo target
- `apps/web`: Next.js/TypeScript frontend
- `apps/api`: FastAPI backend
- `apps/worker`: async document-processing worker
- `packages/contracts`: shared schemas/contracts
- `rules`: versioned insurance/tax rules
- `prompts`: versioned AI prompts
- `docs`: architecture/specifications
- `tests`: synthetic fixtures and integration tests

## Core principles
Documents remain immutable. Practices are logical graph entities, not physical folders. A single receipt can be split into line items and related to multiple people/events.

AI is deterministic-first: rules and exact identifiers before Rizzo Flow, embeddings or LLM reasoning.

## AI stack
- LM Studio via OpenAI-compatible API
- configured primary model: `qwen3.8-27b-abliterated-mtplx-optimized-speed`
- recommended vision model: Qwen3-VL-8B
- configurable embedding model
- Rizzo Flow for fast typed decisions

## Security
Designed for LAN deployment. Authentication is mandatory; no cloud OCR/LLM by default. Backups are encrypted locally before upload.

Start with `docs/IMPLEMENTATION_PLAN.md` and `TODO.md`.

## Local development

Copy `.env.example` to `.env` and adjust only local/LAN endpoints and model IDs.
`docker compose up --build` starts PostgreSQL, Redis, the FastAPI API, the ARQ
worker and the Next.js web UI. Open `http://localhost:3000` for the Inbox and
`http://localhost:8000/docs` for the generated API contract.

The current foundation provides immutable PDF/PNG/JPEG ingestion with binary
MIME sniffing, SHA-256 duplicate detection, PostgreSQL persistence, a queued
native-PDF extraction/classification job with a local Tesseract fallback for
image uploads and text-poor PDFs, household/member creation, LM Studio
model discovery, and a real Inbox. Prescription and invoice extraction use
versioned Pydantic schemas and local LM Studio only; every invocation records
model/prompt/input-hash provenance. Exact identity and compatible service/date
signals can create an explainable proposed `MedicalEvent`; ambiguous cases
remain review tasks.

Use the **Famiglia** panel to create a household and household members before
uploading clinical documents. Fiscal codes are normalized and shape-validated
at the API boundary; their use never collapses patient, payer and fiscal-holder
roles into a single identity.

The Medical Event workspace uses XYFlow to show persisted document links,
confidence and evidence. Its insurance panel evaluates the versioned 2026
`specialist_and_diagnostics` rule as a **candidate only**, displaying missing
documentation rather than claiming a reimbursement. Open review tasks can be
resolved manually through the workspace.

## Privacy

Keep `.env` out of source control. Model endpoints must be local or trusted
LAN endpoints; normal application logs must not include document text or
clinical fields.

## Validation

The containerized test suite uses synthetic data and validates immutable
storage/MIME rejection, fiscal-code normalization, local OCR fallback, and
positive and negative prescription-to-invoice link scoring. It also executes
the household/member API flow against PostgreSQL with cleanup. Run it with
`docker compose run --rm api pytest -q`; lint runs with
`docker compose run --rm api ruff check .`.

GitHub Actions runs the same Compose configuration, full container build,
PostgreSQL-backed tests and Ruff checks on each push and pull request.
Material actions create privacy-preserving audit events that store only opaque
entity identifiers and operational metadata.

## LAN authentication

Authentication is intentionally disabled for local development. Before exposing
the service on a LAN, set `AUTH_ENABLED=true`, an Argon2 value in
`AUTH_PASSWORD_HASH`, and a high-entropy `SESSION_SECRET` in the untracked
`.env` file. The API then requires a signed `HttpOnly`, `SameSite=Lax` session
cookie for all application routes; health checks and login remain available for
bootstrap. Never commit the password hash or session secret.

## Watched directory

Copy supported files into `WATCH_DIRECTORY` (default: `data/inbox`). The ARQ
worker observes it once per minute and waits for two unchanged scans before
ingestion, avoiding partial writes. Accepted files are immutably stored and
then moved to `data/inbox/processed`; unsupported input is moved to
`data/quarantine`.

Supported originals are PDF, PNG, JPEG, TIFF, and HEIC. TIFF and HEIC pages
are normalized to temporary PNG files only for local OCR; their stored
originals remain unchanged.

The processing worker creates an idempotent, bounded PNG thumbnail from the
first PDF page or raster original. It is available at
`GET /api/v1/documents/{document_id}/thumbnail` once processing has started.

## Document viewer and archive names

Tesseract OCR persists word-level bounding boxes on each document page. The
viewer loads page data from `GET /api/v1/documents/{document_id}/pages` and
shows the recognized terms alongside the thumbnail. After processing, each
document receives a deterministic logical name (`date_type_hash.ext`) while
retaining the immutable original and source filename. Exact SHA-256 duplicates
are linked and are not processed again during re-scans.

## Pharmacy

Pharmacy receipts are represented as atomic `ReceiptLine` records with distinct
patient and payer fields. The local AIFA-compatible CSV at `AIFA_CATALOG_PATH`
(default `/data/aifa/catalog.csv`) can be imported through
`POST /api/v1/pharmacy/catalog/import` and is refreshed weekly by the worker.
Nine-digit AIC values are validated against that catalog. Receipt-line matching
uses AIC first, then a conservative medicine-name fallback; unresolved or
patient/payer-conflicting lines create review tasks rather than assumptions.

## Insurance 2026

The reviewed local rule set in `rules/insurance/2026.yml` evaluates coverage
categories, required evidence, diagnosis policy, physiotherapy, dental, lenses,
and hospitalization pre/post windows. It applies configured limits, deductibles
and coinsurance only to candidates with complete evidence. Export a local,
human-review-required PDF summary with
`GET /api/v1/medical-events/{event_id}/insurance-package`.

The synthetic vertical-slice test verifies prescription and invoice structured
extraction, household resolution, explainable matching, and proposed
`MedicalEvent` creation. The Inbox exposes the persisted extracted JSON,
assigned patient, document date, and invoice total for human verification.
