# ADR-002: Practices are graph entities, not folders

**Status:** accepted

Physical files are immutable and stored once. Medical events, claims and tax allocations are logical graph structures referencing documents or expense lines.

This enables:
- one receipt with multiple patients/events;
- insurance plus residual 730 handling;
- reclassification without file copies;
- auditable links and manual overrides;
- immutable source evidence.
