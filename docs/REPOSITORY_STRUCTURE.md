# Repository Structure

```
apps/
  api/        FastAPI HTTP API and domain/application services
  web/        Next.js UI
  worker/     asynchronous processing jobs
packages/
  contracts/  generated/shared contracts
docs/         product, architecture and operational specifications
rules/
  insurance/  insurance rule sets by plan/year
  tax/        tax rule sets by tax year
prompts/      versioned LLM/Rizzo task prompts
tests/
  fixtures/   synthetic/anonymized document fixtures
data/         runtime-only, gitignored
```

Future backend package boundaries:
```
app/
  api/
  core/
  db/
  domain/
  services/
    ingestion/
    documents/
    ocr/
    ai/
    identity/
    linking/
    drugs/
    insurance/
    tax/
    reconciliation/
    export/
  repositories/
  workers/
```

Domain code must not depend directly on FastAPI, LM Studio, Rizzo Flow or storage implementations. Use ports/adapters so providers remain replaceable.
