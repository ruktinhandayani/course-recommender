# Security and HTTPS Deployment

## Runtime Shape

Use the standalone console behind an HTTPS reverse proxy:

```text
Browser
  -> HTTPS reverse proxy
  -> FastAPI ML console/API on the private host or Docker network
  -> local artifacts and data directories
```

The React frontend must not contain API keys, HMAC secrets, or session secrets.

## Admin Console Authentication

The `/ui/api/*` console endpoints use an HTTP-only admin session cookie.

Required production settings:

```text
CRE_ML_ENABLE_TEST_UI=true
CRE_ML_ADMIN_USERNAME=admin
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
CRE_ML_SESSION_SECRET=<long-random-secret>
CRE_ML_SESSION_COOKIE_SECURE=true
CRE_ML_TEST_UI_ORIGINS=https://your-console-domain.example
CRE_UI_API_BASE_URL=https://your-api-domain.example
```

Generate `CRE_ML_ADMIN_PASSWORD_HASH` with:

```bash
python3 scripts/hash_admin_password.py
```

or, after building the backend image:

```bash
docker run --rm -it cre-ml-service:pre-mvp python scripts/hash_admin_password.py
```

Do not deploy with a plaintext admin password, placeholder API keys, or a placeholder session secret.

## Service-to-Service API Security

The integration endpoints remain separate from the console endpoints:

```text
GET /recommendations/export
GET /recommendations/user/{user_id}
```

These endpoints still require:

```text
Authorization: Bearer ...
X-Request-Id: ...
X-Timestamp: ...
X-Signature: ...
```

Keep `CRE_ML_API_KEY` and `CRE_ML_HMAC_SECRET` server-side only.

## Reverse Proxy Checklist

Configure Nginx, Caddy, Traefik, or another proxy to:

```text
- terminate TLS/HTTPS
- redirect HTTP to HTTPS
- pass Host and X-Forwarded-* headers
- expose only the public HTTPS port
- keep artifact/data directories private
- set request size and timeout limits
- proxy the admin console only over HTTPS
- set `CRE_ML_SESSION_COOKIE_SECURE=true` when HTTPS is active
```

For public domains, use Let's Encrypt. For private internal deployments, use an internal CA certificate.

## Privacy Checklist

```text
- avoid raw employee ID in operational logs
- do not log admin passwords, API keys, HMAC secrets, or session cookies
- restrict export review, refresh, and raw response pages to admin users
- rotate secrets before production use
- keep CORS origins limited to the real console domain
```
