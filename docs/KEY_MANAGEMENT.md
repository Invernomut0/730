# Backup key management

`BACKUP_ENCRYPTION_KEY` is a URL-safe base64 encoding of exactly 32 random
bytes. Generate it on the trusted host with a cryptographically secure tool and
store it in a password manager or offline secret store, never in Google Drive,
the backup folder, source control, screenshots, or application logs.

Set the key only in the untracked `.env` file used by the API/backup command.
The application refuses missing, malformed, or non-256-bit keys. Keep at least
two controlled recovery copies in separate physical or administrative domains.

Before rotating a key, verify every existing archive with
`healthdocs-verify-backup <archive.hdbak>`. Create a new archive with the new
key, verify it, upload only the verified ciphertext, then record which key ID
(not the key itself) protects each archive. Retain the old key until all of its
archives have passed their documented retention period.

If a key is exposed, assume every archive encrypted with it is exposed: stop
uploads, create and verify a new backup using a replacement key, revoke any
Google access token, and investigate access to the affected storage location.