# Security and Privacy

HealthDocs stores sensitive health, tax and payment information. LAN is not trusted by default.

## Requirements
Authentication, secure session cookies, CSRF protection, modern password hashing, login rate limiting, least privilege, strict MIME/size checks, path-traversal defense, no execution of uploads, sanitized logs and auditable material actions.

## AI
Cloud OCR/LLM disabled by default. LM Studio/Rizzo Flow must remain local or LAN-only. Only non-personal public identifiers may be sent to approved external data sources.

## Google Drive backup
Archive locally -> encrypt locally with authenticated encryption -> upload opaque encrypted artifact. Never store the encryption key in the same Drive/archive.

## Secrets
Never commit secrets. Use environment variables/secret files excluded from git.

## HTTPS on a LAN
Use the isolated Caddy deployment in `docker-compose.lan.yml`; it exposes only
HTTPS and keeps all application and data services on the private Compose
network. Follow `docs/HTTPS_LAN.md` to enable authentication, trust the local
CA only on managed devices, and restrict the host firewall.

## Retention
Originals immutable; deletions explicit/auditable. Derived OCR and embeddings may use separate retention because they are reproducible.
