# Architecture

## Services
- **web**: Next.js, React, TypeScript, Tailwind, shadcn/ui.
- **api**: FastAPI, Pydantic, SQLAlchemy, Alembic.
- **worker**: persistent async queue for OCR/AI/linking/rules.
- **postgres**: primary data store; pgvector optional.
- **redis**: queue/coordination.
- **lm-studio**: external LAN service.
- **rizzo-flow**: fast typed-decision service where useful.

## Pipeline
```
Inbox
 -> hash/dedupe
 -> native text extraction
 -> OCR
 -> document classification
 -> structured extraction
 -> normalization
 -> AIC/domain enrichment
 -> identity resolution
 -> document linking
 -> MedicalEvent clustering
 -> insurance evaluation
 -> reimbursement reconciliation
 -> tax evaluation
 -> precompiled reconciliation
 -> review/export
```

## Decision order
1. deterministic rules and exact identifiers;
2. household identity matching;
3. domain lookup;
4. temporal scoring;
5. Rizzo Flow;
6. embeddings;
7. LM Studio reasoning;
8. human review.

## Reliability
Every processing stage is idempotent, persisted and replayable. Persist model id, prompt version, schema version and rule-set version.

## Storage
Originals are immutable. Derived assets are reproducible. Diagnoses must not appear in physical filenames.
