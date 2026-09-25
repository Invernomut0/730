# AI Pipeline

## Main model
Default: Qwen3.5-27B via LM Studio. Use for structured extraction, difficult cross-document reasoning and explanations.

## Vision
Default: Qwen3-VL-8B. Use when native text/OCR is insufficient or layout/image understanding is required.

## Embeddings
Configurable through LM Studio. Embeddings support candidate retrieval; never use them alone to confirm links.

Set `LMSTUDIO_EMBEDDING_MODEL` to a locally loaded OpenAI-compatible embedding
model. HealthDocs sends a non-empty batch to `POST /embeddings` and rejects
responses with missing, non-finite, duplicated, or dimensionally inconsistent
vectors. The provider keeps input text in memory only for the request and does
not emit it to application logs.

## Rizzo Flow
Preferred for fast typed decisions such as document type, diagnosis presence, likely coverage category, same-event likelihood and review requirement.

Fallback to main LLM when evidence is insufficient, confidence is low or generative extraction is required.

## Structured output
All extraction uses versioned JSON Schema/Pydantic models. Invalid output gets bounded retry, then ReviewTask.

## Prompt registry
Prompts live under `prompts/<task>/vN.md`. Store prompt version, model id, input hash and schema version per execution.

## Privacy
No document body, diagnosis, fiscal code or OCR text may leave the LAN.
