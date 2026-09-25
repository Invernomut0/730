# Shared contracts

This package will hold generated/shared API schemas and enums used by web, API and worker.

Canonical backend domain models remain Pydantic/OpenAPI. TypeScript clients should be generated from OpenAPI rather than copied manually, to prevent schema drift.
