# API Specification

Base: `/api/v1`.

## Documents
POST /documents
GET /documents
GET /documents/{id}
POST /documents/{id}/reprocess
PATCH /documents/{id}/classification

## Household
GET/POST /households
GET/POST/PATCH /household-members

## Medical events
GET/POST /medical-events
GET /medical-events/{id}
POST /medical-events/{id}/documents
DELETE /medical-events/{id}/documents/{document_id}
POST /medical-events/{id}/confirm

## Insurance
GET /insurance/plans
GET/POST /insurance/claims
POST /insurance/claims/{id}/evaluate
POST /insurance/claims/{id}/reimbursements

## Drugs
GET /drugs/aic/{code}
POST /drugs/catalog/sync

## Review
GET /review-tasks
POST /review-tasks/{id}/resolve

## Tax
GET /tax/{year}/summary
POST /tax/{year}/evaluate
POST /tax/{year}/precompiled/import
GET /tax/{year}/reconciliation

## System
GET/PUT /settings/models
GET /health
GET /health/ai
GET /jobs

FastAPI-generated OpenAPI is canonical once endpoints exist.
