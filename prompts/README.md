# Prompt Registry

Prompts are versioned assets, never large inline strings.

Planned:
- document-classifier/v1.md
- prescription-extractor/v1.md
- report-extractor/v1.md
- invoice-extractor/v1.md
- receipt-extractor/v1.md
- event-linker/v1.md

Every execution stores task, prompt version, model id, schema version and input hash.

## Rizzo Flow decision contract

When `RIZZO_FLOW_ENABLED=true`, HealthDocs sends a batch to the local endpoint
`POST {RIZZO_FLOW_BASE_URL}/decisions` with this shape:

- request: `{"decisions": [{"task", "prompt", "schema"}]}`;
- response: `{"decisions": [{"output": {}}]}` in the same order and count.

Each output is validated by the task's Pydantic schema. A connection error,
wrong item count, malformed JSON output, or schema-validation failure is stored
as a failed `AIExecution` and falls back to the configured local LM Studio
provider. Prompt text is never written to audit records.
