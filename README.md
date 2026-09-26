## Association decisions

Each proposed medical event can be approved or rejected from the workspace. A
rejection requires an explanation and is recorded in the audit trail. Approved
associations leave the proposed-relations queue and appear in a separate,
selectable approved-relations archive.

**Rifai le relazioni da zero** removes every existing event, link and related
link review, then rebuilds proposals from the persisted prescription/invoice
structured data—regardless of a stale document pipeline state. It never deletes
extracted records, pages, document metadata, or original files, and it never
queues OCR or document extraction. The result reports created links and review
proposals; when neither can be created, it explicitly confirms that no safe
match had sufficient patient/date/service evidence. A database uniqueness
constraint on each prescription/invoice document pair prevents duplicate links.

When imported or rebuilt documents remain in `STORED` / `UNKNOWN`, use
**Avvia analisi documenti** above the Inbox. It queues each non-duplicate
stored document, or a document visibly stuck in `EXTRACTING`, for the local
worker. This makes stalled analyses recoverable without modifying the immutable
original.
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

Rizzo Flow is optional and disabled by default. If enabled, it receives local
schema-constrained batches at `POST /decisions`; malformed or unavailable Rizzo
responses fall back to the configured local LM Studio model. Each provider
attempt is recorded as an `AIExecution` with opaque input hash, prompt/schema
versions, status, and duration—never document content.

Set `LMSTUDIO_EMBEDDING_MODEL` only to a model served locally by LM Studio.
Embedding responses are validated for finite, consistently sized vectors and
are reserved for candidate retrieval; they cannot independently confirm a
medical-document link.

The versioned document-classifier calibration dataset is wholly synthetic and
ships with the API image. Its typed loader rejects invalid, duplicate, or
incomplete data before a future local Rizzo evaluation can run.

With `RIZZO_FLOW_ENABLED=true` and a trusted local endpoint, run
`docker compose run --rm api evaluate-rizzo --minimum-accuracy 0.95` to measure
Rizzo directly. The command has no LM Studio fallback, returns a non-zero status
when the threshold is not met, and emits no calibration input text.

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

The API accepts browser requests only from the local web origins
`http://localhost:3000` and `http://127.0.0.1:3000` by default. Set
`CORS_ORIGINS` as a JSON list only when adding another trusted local web origin.

The web UI uses a local, responsive editorial design system: no external fonts
or assets are loaded. Its dossier cards, high-contrast states, and responsive
forms preserve usability for document review on desktop and tablet screens.

The current foundation provides immutable PDF/PNG/JPEG ingestion with binary
MIME sniffing, SHA-256 duplicate detection, PostgreSQL persistence, a queued
native-PDF extraction/classification job with a local Tesseract fallback for
image uploads and text-poor PDFs, household/member creation, LM Studio
model discovery, and a real Inbox. Prescription and invoice extraction use
versioned Pydantic schemas and local LM Studio only; every invocation records
model/prompt/input-hash provenance. Exact identity and compatible service/date
signals can create an explainable proposed `MedicalEvent`; ambiguous cases
remain review tasks.

The deterministic classifier gives explicit fiscal markers (for example
`FATTURA`, VAT and taxable-total fields) priority over an incidental
`Ricetta`/`Quota Ricetta` mention on a healthcare invoice.

Uploads are size-checked before and during buffering, verified by binary
signature rather than HTTP headers, and atomically stored with private file
permissions. Adjust the multipart allowance with
`MAX_UPLOAD_REQUEST_OVERHEAD_BYTES` only when a trusted proxy adds larger
request metadata.

Structured extraction uses `LMSTUDIO_EXTRACTION_MODEL`, which defaults to the
small local `qwen/qwen3-vl-8b` model. It allows 1800 seconds by default; the
configured large fallback is used only when that local extraction fails. Exact
duplicate uploads are retained as immutable records but deliberately do not
invoke OCR or the LLM a second time.

Documents classified as `OTHER` or pharmacy receipts use a separate, lenient
generic clinical schema. If a strict prescription, invoice, or report schema is
invalid, the pipeline retries with this persistent fallback before opening a
review. It retains supported patient, date, provider, summary, findings,
medications, laboratory tests, and services without creating clinical links.

`LMSTUDIO_MAIN_MODEL` retains the primary local model identifier for health and
legacy integrations. The 27B model configured by `LMSTUDIO_RELATION_MODEL` judges only
prescription/invoice pairs that already pass deterministic patient and 0–30 day
chronology gates; it can create a proposed relationship but never override those
gates. `LMSTUDIO_SIMPLE_MODEL` is reserved for one cheap, audited fallback:
classifying a document which the deterministic rules leave as `UNKNOWN`.

The dedicated **Impostazioni** tab exposes non-secret runtime model routing for
document analysis, uncertain classification, extraction fallback, relationship
matching, and local Rizzo Flow. **Stop tutti i job** pauses worker intake,
removes queued ARQ work, and safely returns nonterminal documents to `STORED`.
An in-flight local model request is allowed to finish so that no partially
committed document state is produced; use **Riprendi job** before starting new
analysis.

Each original document in the Inbox has a **Rinforza analisi** action. It
removes only that document's derived extraction, review, and generated link
data, then queues a fresh local analysis. The action is unavailable while that
document is already processing or when it is an exact duplicate.
The per-document reanalysis and deletion actions remain side by side on desktop
rows for fast operational review.

The local web origins `http://localhost:3000` and `http://127.0.0.1:3000` can
both save these settings through the API's CORS-protected `PUT` endpoint.

When opening a document, the right-hand summary panel presents the extracted
patient name, date, diagnostic question, document type, clinician, requested
service, and a separate **Farmaci prescritti** field whenever a prescription
contains itemized medicines.

The Inbox constrains long filenames to the document-name column, displays an
ellipsis when needed, and exposes the full name through the native tooltip; file
names never overlap document type, processing state, size, or actions.
Pipeline state badges are color-coded: neutral for stored items, blue for active
processing, green for completed analysis, amber for review, and red for errors.
While documents are active, the Inbox polls their server state every five seconds
without a page reload and shows a phase-based timebar. Its remaining duration is
an explicitly labelled estimate based on elapsed analysis time; it changes to
“stima in aggiornamento” rather than presenting a false completion time when a
local model exceeds the typical duration.

Document relationships require a matching clinical specialty or a shared
meaningful service term. Generic wording such as "visita" is never sufficient;
the local worker processes at most four structured documents concurrently to
increase throughput while retaining the configured local-model timeout.

For prescriptions, the extraction contract separately lists every prescribed
drug and every requested individual laboratory test. Invoices separately list
billed drugs and laboratory tests. A prescription-to-invoice relation is blocked
when even one listed drug or test has no distinct matching billed line; the
large relation model cannot override this safety gate.

When a prescription contains one or more requested laboratory tests (including
Italian `90.*` service codes), the viewer presents **Esami di laboratorio** as
the requested service and lists the individual **Esami richiesti** separately.
When a prescription contains medicines but no other requested service, the
viewer presents **Farmaci prescritti** as the requested-service category and
lists the extracted medicines separately.

Prescription normalization treats Italian laboratory service codes beginning
with `90.` and explicit analytes (including `VITAMINA D (25 OH)`) as laboratory
tests, even if a local model initially places one in the drug list. Printed AIC
codes and dosage forms identify medicines instead.

Medical reports with a printed laboratory table are identified as
`LABORATORY_RESULTS`. The extraction preserves each printed analyte, result,
unit, reference range, and explicit flag without interpreting the result or
making a clinical diagnosis.

For clinical reports, explicitly printed performed visits and specialist
examinations are retained as `documented_services` and shown as **Prestazione
documentata** in the viewer. This preserves headings such as `VISITA DI
CONTROLLO - GASTROENTEROLOGIA` without treating them as a future request.

`LMSTUDIO_REQUEST_TIMEOUT_SECONDS` defaults to `1800` (30 minutes), allowing
large local models to complete long structured extractions without premature retry.
The ARQ worker timeout covers the complete local pipeline (optional small-model
classification, extraction, and fallback), rather than its five-minute default.
If a worker is cancelled during an active phase, the document returns to
`STORED` instead of remaining indefinitely in `STRUCTURING`; it can then be
started again safely. Each resumed worker attempt receives a fresh analysis
timestamp so the Inbox timebar describes the active attempt rather than a
cancelled one.

LM Studio reasoning models that leave the OpenAI JSON-schema `content` field
empty are requested in text mode instead; the API then parses JSON only and
validates it against the same Pydantic extraction schema before persistence. The
schema is included directly in the local prompt in this compatibility mode.
Unambiguous Italian dates returned by the model (`GG/MM/AAAA` and `GG-MM-AAAA`)
are normalized before schema validation; ambiguous date formats remain rejected.

## Resetting local application data

The bottom of the Inbox contains an **Azzera database** control. Type `RESET`
to enable it: the action permanently clears every application table (including
documents, family, extraction records, review tasks, audit events, and local
catalog imports) while preserving the database schema. It deliberately does
not remove files from `data/`; remove those separately only when required.

Each document row and family card also has an **Elimina** action. After browser
confirmation, document deletion removes its dependent records, exact duplicate
records, original, and thumbnail; household deletion removes its members and
all document records associated with those members.

Use the **Famiglia** panel to create a household and household members before
uploading clinical documents. Fiscal codes are normalized and shape-validated
at the API boundary; their use never collapses patient, payer and fiscal-holder
roles into a single identity.

The Medical Event workspace uses XYFlow to show persisted document links,
confidence and evidence. Its insurance panel evaluates the versioned 2026
`specialist_and_diagnostics` rule as a **candidate only**, displaying missing
documentation rather than claiming a reimbursement. Link reviews show the two
documents, score, supporting evidence and conflicts; the operator opens both
originals before either creating an auditable confirmed event or marking the
suggestion as unrelated. Each link review also displays the extracted document
type, prescription and invoice services, document dates, patient, invoice total,
and the recorded matching signals. Until an operator confirms the episode, it
is explicitly proposed to neither insurance nor the 730 flow; those independent
evaluations occur only after confirmation. Reviews are automatically resolved when either
referenced document has been deleted, so the queue never presents an action that
cannot be completed.

Graph document nodes use the logical, human-readable filename and can be
clicked to open the original-document viewer with its extracted fields. Event
titles use the first extracted requested or invoiced service rather than a
generic fixed name; legacy generic titles are corrected on their next API read.
A reimbursement estimate is displayed only when the invoice
contains a structured total; otherwise the UI says that the estimate is not
available rather than presenting a misleading €0 amount.

The insurance workspace always separates the **documented invoice expense**
from the **estimated reimbursement**. Until the provider network is verified,
the estimate uses the reviewed out-of-network policy terms and explains that
assumption; a zero reimbursement can therefore be traced to the applicable
deductible or coinsurance rather than confused with a missing invoice amount.

When local extraction cannot classify a document, the review queue provides
**Apri originale e completa manualmente**. It opens the immutable original and
its available data, then records the operator-supplied document type, date,
patient, service, provider and (for invoices) total as a structured manual
entry. The original remains unchanged, the review is auditable, and ordinary
linking resumes only after those fields are saved.

Invoice-to-prescription links require a strict 0–30 day window: an invoice dated
before its prescription or more than 30 days after it is excluded from matching,
cannot be manually confirmed, and any legacy proposal is automatically archived
with an audit event.

Reviews for incomplete document classification are distinct from link reviews:
they provide the single original for inspection and a **Riprova elaborazione**
action. The retry clears obsolete OCR coordinates, requeues local extraction,
and creates a new review only if the new local attempt still cannot complete.

## Privacy

Keep `.env` out of source control. Model endpoints must be local or trusted
LAN endpoints; normal application logs must not include document text or
clinical fields.

## Encrypted backup

Set a unique `BACKUP_ENCRYPTION_KEY` in the untracked `.env`, then run
`docker compose run --rm api healthdocs-backup`. Verify the resulting `.hdbak`
file with `healthdocs-verify-backup` before using `healthdocs-upload-backup` to
send the ciphertext to Google Drive. Local archives contain both the immutable
data volume and a PostgreSQL custom dump; verification authenticates the archive
and runs a non-destructive `pg_restore --list` check on that dump. Follow
`docs/KEY_MANAGEMENT.md` for key generation, rotation, recovery copies, and
incident handling.

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

Failed login attempts are throttled in Redis by a non-reversible client-address
hash. Configure `LOGIN_RATE_LIMIT_ATTEMPTS` and
`LOGIN_RATE_LIMIT_WINDOW_SECONDS` in the untracked `.env` for LAN policy.

## HTTPS LAN deployment

Use `docker-compose.lan.yml` for LAN deployment, not the development Compose
file. It exposes only Caddy on port 443 and provides a local CA for
`LAN_HOSTNAME`; API, web, database, Redis, and worker ports remain private.
See `docs/HTTPS_LAN.md` for the required authentication settings, CA trust, and
firewall verification steps.

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

Native PDF extraction and Tesseract OCR persist normalized word-level bounding
boxes on each document page. The viewer loads page data from
`GET /api/v1/documents/{document_id}/pages` and overlays those local coordinates
on the thumbnail. After processing, each document receives a deterministic
logical name (`date_type_hash.ext`) while retaining the immutable original and
source filename. Exact SHA-256 duplicates are linked and are not processed again
during re-scans.

Opening a document from the Inbox, a review, or a graph node displays this data
in a floating, draggable viewer layer. This keeps the current work context
visible; drag its header to reposition it and use **Chiudi** to return to the
underlying workflow.

Medical reports are structured locally into report date, patient, provider,
diagnostic evidence, requested visits, documented operations, and explicit
follow-up activities. Every extracted item keeps page/source/confidence evidence
and is displayed in the document viewer. Numeric bounding-box coordinates emitted
as strings by a local model are normalized before validation, so otherwise valid
extractions complete automatically instead of creating a manual retry review.

Patient resolution prioritizes an exact fiscal code. When no local fiscal-code
match exists but the extracted full name (including surname-first order) has one
unique household match, the document is assigned to that person and a fiscal-code
conflict is recorded for human review.

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

## Reimbursements and tax

Reimbursements and their allocations are persisted separately from expenses,
enabling auditable out-of-pocket reconciliation at line level. Tax allocations
require a reviewed, sourced `TaxRuleSet` and traceable `PaymentEvidence`; the
engine deliberately preserves the gross amount unless the reviewed rule
explicitly states that reimbursements reduce the tax base.

## Pre-filled 730

Import a local UTF-8 CSV with `expense_date`, `amount`, `description`, and an
optional `fiscal_code`. HealthDocs normalizes rows, matches only unique local tax
allocations, and presents unmatched or ambiguous entries in the Precompilata 730
panel; it never uses authenticated scraping or SPID/CIE credentials.

The synthetic vertical-slice test verifies prescription and invoice structured
extraction, household resolution, explainable matching, and proposed
`MedicalEvent` creation. The Inbox exposes the persisted extracted JSON,
assigned patient, document date, and invoice total for human verification.
