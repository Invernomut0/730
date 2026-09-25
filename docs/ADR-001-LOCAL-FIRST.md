# ADR-001: Local-first processing

**Status:** accepted

Health documents contain sensitive health and tax data. OCR, classification, extraction, embeddings and reasoning must run locally/on the trusted LAN. External network calls are restricted to public non-personal datasets/identifiers and encrypted backup transport.

Consequences:
- LM Studio is the primary LLM/VLM provider.
- No cloud OCR or hosted LLM fallback by default.
- Background jobs must tolerate model host unavailability.
- Backup artifacts are encrypted before leaving the host.
