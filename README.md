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
- recommended primary model: Qwen3.5-27B
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
native-PDF extraction/classification job, household/member creation, LM Studio
model discovery, and a real Inbox. Prescription and invoice extraction use
versioned Pydantic schemas and local LM Studio only; every invocation records
model/prompt/input-hash provenance. Exact identity and compatible service/date
signals can create an explainable proposed `MedicalEvent`; ambiguous cases
remain review tasks.

## Privacy

Keep `.env` out of source control. Model endpoints must be local or trusted
LAN endpoints; normal application logs must not include document text or
clinical fields.
