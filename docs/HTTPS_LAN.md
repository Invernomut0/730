# HTTPS LAN deployment

Use `docker-compose.lan.yml` for a trusted LAN deployment. It publishes only
TCP 443 through Caddy; PostgreSQL, Redis, the API, worker, and Next.js service
remain internal to the Compose network. Do not combine this file with the
development `docker-compose.yml`.

## Prepare the host

1. Reserve a stable private IP address for the host and configure an internal
   DNS name, for example `healthdocs.lan`, pointing to it. Set that name in the
   untracked `.env` as `LAN_HOSTNAME=healthdocs.lan`.
2. Set `APP_ENV=production`, `AUTH_ENABLED=true`, a new Argon2 hash in
   `AUTH_PASSWORD_HASH`, and a unique high-entropy `SESSION_SECRET`. Never copy
   development secrets into this deployment.
3. Restrict the host firewall to TCP 443 from the required LAN segment. Do not
   publish ports 3000, 8000, 5432, or 6379.
4. Start the isolated stack with
   `docker compose -f docker-compose.lan.yml up --build -d`.

## Trust the local certificate authority

Caddy uses its internal CA (`tls internal`) because a private `.lan` name is
not publicly verifiable. Copy the generated root certificate from the Caddy
container and install it only on managed household devices. On macOS, add it to
the System keychain and set it to **Always Trust**. Remove the certificate from
devices when their access ends.

After the stack starts, the certificate is at
`/data/caddy/pki/authorities/local/root.crt` inside the `caddy` service. Copy
it with `docker compose -f docker-compose.lan.yml cp caddy:/data/caddy/pki/authorities/local/root.crt ./healthdocs-lan-root.crt`.

## Verify and operate

Open `https://<LAN_HOSTNAME>` from a trusted device and verify that the browser
shows the local CA certificate, login is required, and the session cookie is
`Secure` and `HttpOnly`. Confirm that `https://<LAN_HOSTNAME>/api/v1/health`
responds only through Caddy. Keep the Caddy data volume: deleting it rotates
the internal CA and invalidates trusted client certificates.

The reverse proxy intentionally emits no access log directive. Do not add
request-body logging or upload URLs to logs, and do not expose Caddy’s admin
API. Review this setup alongside `docs/SECURITY.md` before each LAN deployment.