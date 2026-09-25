# Security and Privacy

HealthDocs stores sensitive health, tax and payment information. LAN is not trusted by default.

## Requirements
Authentication, secure session cookies, CSRF protection, modern password hashing, login rate limiting, least privilege, strict MIME/size checks, path-traversal defense, no execution of uploads, sanitized logs and auditable material actions.

## Upload hardening
The API rejects malformed or clearly oversized declared request bodies before
buffering them, then enforces the exact file-size limit while reading. MIME type
is determined from supported binary signatures, never the client header.
Originals are written through a private temporary file and atomically published
with `0600` permissions; partial writes cannot appear as stored documents.

## Login and logging
When authentication is enabled, Redis enforces a fixed login-attempt window per
opaque client-address hash. Set `LOGIN_RATE_LIMIT_ATTEMPTS` and
`LOGIN_RATE_LIMIT_WINDOW_SECONDS` to suit the trusted LAN; Redis unavailability
fails closed for login rather than silently disabling protection. Structured log
contexts are recursively redacted for passwords, secrets, tokens, fiscal codes,
and document text/content before handler output.

## AI
Cloud OCR/LLM disabled by default. LM Studio/Rizzo Flow must remain local or LAN-only. Only non-personal public identifiers may be sent to approved external data sources.

## Google Drive backup
Archive locally -> encrypt locally with authenticated encryption -> upload opaque encrypted artifact. Never store the encryption key in the same Drive/archive.

`healthdocs-backup` creates a local AES-256-GCM `.hdbak` archive containing the
immutable data volume and a PostgreSQL custom dump. It can be authenticated and
inspected without restoring with `healthdocs-verify-backup`, which also runs
`pg_restore --list` against the decrypted dump.
`healthdocs-upload-backup` accepts only that encrypted extension and uses a
resumable Google Drive upload. The Drive token may upload ciphertext but never
receives the encryption key. Give `GOOGLE_DRIVE_ACCESS_TOKEN` only a dedicated,
least-privilege Drive folder and rotate or revoke it independently of backup
keys. See `docs/KEY_MANAGEMENT.md`.

## Secrets
Never commit secrets. Use environment variables/secret files excluded from git.

## HTTPS on a LAN
Use the isolated Caddy deployment in `docker-compose.lan.yml`; it exposes only
HTTPS and keeps all application and data services on the private Compose
network. Follow `docs/HTTPS_LAN.md` to enable authentication, trust the local
CA only on managed devices, and restrict the host firewall.

## Retention
Originals immutable; deletions explicit/auditable. Derived OCR and embeddings may use separate retention because they are reproducible.
