# CRE Project Handover

This document is the short operational handover for CRE, Course Recommendation for Employees. Use it when giving the project to another developer, operator, or VPS administrator.

For full details, read:

- `README.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/SECURITY_DEPLOYMENT.md`
- `docs/03_api_contract.md`

## What The Project Is

CRE is a standalone ML recommendation service and admin console.

It contains:

- FastAPI backend service: `cre-ml-service`
- React admin console served by Nginx: `cre-ml-ui`
- Batch-generated recommendation export
- Admin login using an HTTP-only session cookie
- Signed service-to-service recommendation API using bearer token and HMAC

The current app is an admin/research console, not the final LMS learner dashboard.

## Required Handover Files

The receiver needs the repository plus these ignored runtime folders:

```text
data/
course_recommender_artifacts_final/
```

The `data/` folder contains local input CSV data. The `course_recommender_artifacts_final/` folder contains the final-run model artifacts, generated tables, and recommendation exports.

Do not hand over real `.env` files through git. Transfer production secrets through a secure channel.

## Important Files

```text
README.md                         Project overview and common commands
docs/DEVELOPER_GUIDE.md           Local run, development, testing, and VPS deployment
docs/SECURITY_DEPLOYMENT.md       HTTPS, admin session, HMAC, and security checklist
.env.example                      Local environment template
.env.production.example           Production environment template
docker-compose.yml                Full Docker stack
Dockerfile                        Backend Docker image
frontend/Dockerfile               Frontend production Nginx image
scripts/hash_admin_password.py    Admin password hash generator
scripts/generate_export.py        Recommendation export generator
scripts/sign_request.py           Signed API request helper
```

## Machine Requirements

Recommended development machine:

```text
Docker Desktop or Docker Engine with Compose
Git
Node.js, only for frontend development outside Docker
Python 3.11, only for backend development outside Docker
```

Recommended VPS baseline:

```text
Ubuntu 22.04 or 24.04 LTS
2 CPU cores minimum
4 GB RAM minimum for light testing
Docker Engine and Docker Compose plugin
Nginx or Caddy for HTTPS reverse proxy
Domain name pointing to the VPS
```

## Local Setup From Fresh Copy

From the project root:

```bash
cp .env.example .env
```

Set real values in `.env`:

```env
CRE_ML_API_KEY=<long-random-api-key>
CRE_ML_HMAC_SECRET=<long-random-hmac-secret>
CRE_ML_SESSION_SECRET=<long-random-session-secret>
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
```

Generate an admin password hash:

```bash
docker build -t cre-ml-service:pre-mvp .
docker run --rm -it cre-ml-service:pre-mvp python scripts/hash_admin_password.py
```

Paste the printed value into `.env` as:

```env
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
```

Keep the single quotes because the hash contains `$`.

Start the project:

```bash
docker compose up --build -d
```

Open:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8001
Health:   http://127.0.0.1:8001/health
```

## Local Verification

Check containers:

```bash
docker compose ps
```

Check backend health:

```bash
curl http://127.0.0.1:8001/health
```

Run backend tests:

```bash
docker compose run --rm cre-ml-service python -m pytest tests -q
```

Manual UI smoke test:

1. Open `http://127.0.0.1:5173`.
2. Login as `admin`.
3. Confirm Overview loads.
4. Search for a known employee/user ID.
5. Open Export Review, Evaluation, Refresh, and Raw Response pages.

## Changing The Admin Password

Do not edit only `secrets/cre-admin-password.txt`. That file is only a local reminder if present.

The real login password is controlled by this value in `.env`:

```env
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
```

Generate a new hash:

```bash
docker compose run --rm cre-ml-service python scripts/hash_admin_password.py
```

Update `.env`, then recreate the backend:

```bash
docker compose up -d --force-recreate cre-ml-service
```

## Regenerating Recommendations

The API serves pre-generated recommendation export files from:

```text
course_recommender_artifacts_final/export/
```

Regenerate after changing data, model artifacts, ranking logic, model version, or top-K requirements:

```bash
docker compose run --rm cre-ml-service python scripts/generate_export.py --top-k 20
```

The admin console also has a Refresh page that can trigger the same export regeneration and show live computing logs.

## Production Deployment Summary

Use Docker Compose behind HTTPS reverse proxy.

Production `.env` should come from:

```bash
cp .env.production.example .env
```

Set production values:

```env
CRE_ML_API_KEY=<long-random-api-key>
CRE_ML_HMAC_SECRET=<long-random-hmac-secret>
CRE_ML_SESSION_SECRET=<long-random-session-secret>
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
CRE_ML_REQUIRE_AUTH=true
CRE_ML_ENABLE_TEST_UI=true
CRE_ML_TEST_UI_ORIGINS=https://cre.your-domain.example
CRE_ML_SESSION_COOKIE_SECURE=true
CRE_UI_API_BASE_URL=https://cre.your-domain.example
```

Start on the VPS:

```bash
docker compose up --build -d
```

Keep Docker ports private. The Compose file binds to localhost:

```text
127.0.0.1:8001 -> backend
127.0.0.1:5173 -> frontend
```

Expose the app publicly only through Nginx, Caddy, Traefik, or another HTTPS reverse proxy.

## HTTPS Reverse Proxy Shape

Use one public HTTPS domain if possible:

```text
https://cre.your-domain.example          -> frontend container on 127.0.0.1:5173
https://cre.your-domain.example/ui/api/  -> backend container on 127.0.0.1:8001
https://cre.your-domain.example/health   -> backend container on 127.0.0.1:8001
https://cre.your-domain.example/recommendations/ -> backend container on 127.0.0.1:8001
```

The reverse proxy must:

```text
terminate HTTPS
redirect HTTP to HTTPS
pass Host and X-Forwarded-* headers
keep data and artifact folders private
avoid exposing Docker ports directly
```

Use Let's Encrypt for public domains.

## Security Rules

Required for production:

```text
CRE_ML_REQUIRE_AUTH=true
CRE_ML_SESSION_COOKIE_SECURE=true
real CRE_ML_API_KEY
real CRE_ML_HMAC_SECRET
real CRE_ML_SESSION_SECRET
hashed admin password only
HTTPS enabled
limited CRE_ML_TEST_UI_ORIGINS
```

Never commit:

```text
.env
secrets/
data/
course_recommender_artifacts_final/
API keys
HMAC secrets
admin passwords
session secrets
```

Avoid logging:

```text
raw employee IDs
admin passwords
API keys
HMAC secrets
session cookies
```

## API Integration Notes

The service-to-service endpoints are:

```text
GET /recommendations/export
GET /recommendations/user/{user_id}
```

They require:

```http
Authorization: Bearer {api_key}
X-Request-Id: {request_id}
X-Timestamp: {unix_timestamp}
X-Signature: {hmac_sha256}
```

Generate test headers:

```bash
docker compose exec -T cre-ml-service python scripts/sign_request.py /recommendations/export --query "limit=10"
```

See `docs/03_api_contract.md` for the full response contract.

## Common Troubleshooting

If Docker Compose complains about missing variables, check that `.env` exists and contains:

```text
CRE_ML_API_KEY
CRE_ML_HMAC_SECRET
CRE_ML_ADMIN_PASSWORD_HASH
CRE_ML_SESSION_SECRET
```

If login fails after changing the password, confirm the hash is quoted:

```env
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
```

If the frontend cannot call the backend in production, rebuild the frontend after setting:

```env
CRE_UI_API_BASE_URL=https://cre.your-domain.example
```

Then run:

```bash
docker compose up --build -d cre-ml-ui
```

If recommendations are missing, verify these files exist:

```text
course_recommender_artifacts_final/export/recommendations.csv
course_recommender_artifacts_final/export/recommendation_export_manifest.json
```

If the backend is unhealthy, inspect logs:

```bash
docker compose logs --tail=200 cre-ml-service
```

## Recommended Handover Checklist

Before handing over:

```text
repository source is complete
data/ transferred securely
course_recommender_artifacts_final/ transferred securely
.env.example and .env.production.example are present
real .env is not committed
admin password is shared through secure channel or reset by receiver
Docker stack has been tested
health endpoint returns OK
admin console login works
known employee/user ID search works
deployment domain and VPS access are documented
```

## Current Next Phase

The recommended next development phase is the Pre-MVP LMS/PHP simulator.

That simulator should prove:

```text
signed client can call the CRE export API
paginated sync works
recommendations can be mapped and cached
invalid rows are skipped safely
dashboard can display top recommendations
failed sync does not wipe previous active recommendations
```
