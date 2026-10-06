# Developer Guide

This guide explains how to run, test, develop, and deploy the CRE ML recommendation service and standalone admin console.

The project has two runtime parts:

- `cre-ml-service`: FastAPI backend that serves recommendation data from generated artifacts.
- `cre-ml-ui`: React + TypeScript + Vite admin console for inspecting, evaluating, and refreshing recommendation exports from a browser.

Docker is the preferred development path because the backend depends on Python 3.11 and TensorFlow-related packages.

## Requirements

Install these on the development machine:

- Docker Desktop or Docker Engine with Compose support.
- Node.js only if you want to run the frontend outside Docker.
- Python 3.11 only if you want to run the backend outside Docker.

On Windows PowerShell, use the commands exactly as shown unless you are adapting them for another shell.

## Project Layout

```text
course_recommender/              Backend package: API, service loading, security, export store
course_recommender_artifacts_final/ Generated final model and recommendation export artifacts
data/                            Local dataset inputs
frontend/                        React + TypeScript + Vite admin console
scripts/                         Export generation and request signing helpers
tests/                           Pytest coverage for API and export behavior
docs/                            Architecture and developer documentation
docker-compose.yml               Local full-stack runtime
Dockerfile                       Backend image
frontend/Dockerfile              Frontend image
```

## Environment Configuration

Copy the example env file before running the service with real secrets:

```powershell
Copy-Item .env.example .env
```

Important variables:

```text
CRE_ML_ARTIFACT_DIR=course_recommender_artifacts_final
CRE_ML_DATA_DIR=data
CRE_ML_EXPORT_DIR=course_recommender_artifacts_final/export
CRE_ML_MODEL_VERSION=cre-lstm-attention-h2-seed42-fullmask-v1
CRE_ML_API_KEY=replace-with-real-api-key
CRE_ML_HMAC_SECRET=replace-with-real-hmac-secret
CRE_ML_REQUIRE_AUTH=true
CRE_ML_ENABLE_TEST_UI=false
CRE_ML_TEST_UI_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
CRE_ML_ADMIN_USERNAME=admin
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
CRE_ML_SESSION_SECRET=replace-with-random-session-secret
CRE_ML_SESSION_COOKIE_SECURE=false
CRE_UI_API_BASE_URL=http://127.0.0.1:8001
```

For local Docker Compose, `CRE_ML_ENABLE_TEST_UI` defaults to `true` so the browser UI can call `/ui/api/*`. Those UI endpoints require an admin session cookie. For shared, staging, or production environments, expose them only behind HTTPS and real admin credentials.

Do not commit real `.env` files or secrets.

## Run The Full Project With Docker

Start backend and frontend:

```powershell
docker compose up --build
```

Run in the background:

```powershell
docker compose up --build -d
```

Open:

```text
Frontend UI: http://127.0.0.1:5173/
Backend API: http://127.0.0.1:8001/
API docs:    http://127.0.0.1:8001/docs
Health:      http://127.0.0.1:8001/health
```

Admin login:

```text
username: admin
password: see secrets/cre-admin-password.txt for this local workspace
```

The local `.env` stores only `CRE_ML_ADMIN_PASSWORD_HASH`, not the plaintext password. Generate a new password and hash for every shared or VPS deployment.

Check container status:

```powershell
docker compose ps
```

View logs:

```powershell
docker compose logs -f cre-ml-service
docker compose logs -f cre-ml-ui
```

Stop the stack:

```powershell
docker compose down
```

## Run Backend Only

```powershell
docker compose up --build cre-ml-service
```

The backend binds to:

```text
http://127.0.0.1:8001
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

## Run Frontend Only

If the backend is already running on `http://127.0.0.1:8001`, run the frontend through Docker:

```powershell
docker compose up --build cre-ml-ui
```

Or run it locally:

```powershell
Set-Location frontend
npm install
npm run dev
```

The Docker frontend is a production Nginx static image. Its browser-facing backend base URL is baked in at build time from:

```text
CRE_UI_API_BASE_URL=http://127.0.0.1:8001
```

In Docker Compose this is passed to the frontend build as `VITE_API_BASE_URL`.

## What The Admin Console Shows

The current UI is an admin/research console, not the final LMS learner experience. It is meant to verify that the ML service is alive, inspect recommendation data, review evaluation artifacts, and manually refresh the export.

It includes:

- Login/logout with an HTTP-only admin session cookie.
- Overview page with API health, artifact status, model version, export count, and evaluation cards.
- User Search page with course title, canonical course ID, rank, score, similarity/softmax fields when available, competency, level, and fallback reason.
- Export Review page with paginated export rows.
- Evaluation page backed by generated artifact CSV tables.
- Refresh page that starts export regeneration and polls live computing logs.
- Raw Response page for debugging exact JSON payloads.

The UI calls the admin bridge endpoints:

```text
POST /ui/api/auth/login
POST /ui/api/auth/logout
GET /ui/api/auth/me
GET /ui/api/health
GET /ui/api/recommendations/user/{user_id}
GET /ui/api/recommendations/export
GET /ui/api/evaluation/summary
POST /ui/api/refresh/start
GET /ui/api/refresh/status/{job_id}
```

The production endpoints remain protected by bearer token and HMAC signing:

```text
GET /recommendations/user/{user_id}
GET /recommendations/export
```

## Test The Backend

Run all backend tests inside Docker:

```powershell
docker compose exec -T cre-ml-service python -m pytest tests -q
```

If the service container is not running, use:

```powershell
docker compose run --rm cre-ml-service python -m pytest tests -q
```

The tests cover:

- export store pagination
- invalid cursor handling
- API response contracts
- fixture mode
- per-user recommendation lookup
- missing and invalid security headers
- UI bridge access rules
- admin login/session behavior
- evaluation endpoint response shape

## Test The Frontend

Build the frontend:

```powershell
Set-Location frontend
npm install
npm run build
```

When running through Docker Compose, you can execute the build in the frontend container:

```powershell
docker compose exec -T cre-ml-ui npm run build
```

Manual smoke test:

1. Open `http://127.0.0.1:5173/`.
2. Login with the local admin credentials.
3. Confirm the Overview page shows the backend as available.
4. Search for a known `user_id`, for example one visible in the export preview.
5. Switch between normal and test mode.
6. Load the next export page and confirm the cursor changes.
7. Open Evaluation and Raw Response.

## Generate Recommendation Exports

The API serves pre-generated recommendations from:

```text
course_recommender_artifacts_final/export/recommendations.csv
course_recommender_artifacts_final/export/recommendations_fixture.csv
course_recommender_artifacts_final/export/recommendation_export_manifest.json
```

Generate or refresh the export with Docker:

```powershell
docker compose run --rm cre-ml-service python scripts/generate_export.py --top-k 20
```

Generate with local Python:

```powershell
.\.venv\Scripts\python.exe scripts\generate_export.py --top-k 20
```

Regenerate the export after changing:

- model artifacts
- cleaned dataset CSVs
- ranking logic
- model version
- top-K requirement

## Test Signed Production Endpoints

The production recommendation endpoints require these headers:

```http
Authorization: Bearer {api_key}
X-Request-Id: {request_id}
X-Timestamp: {unix_timestamp}
X-Signature: {hmac_sha256}
```

Generate signed headers:

```powershell
docker compose exec -T cre-ml-service python scripts/sign_request.py /recommendations/export --query "limit=10"
```

Then call the endpoint with the generated headers. The signed path and query must match the request exactly.

## Local Python Development

Use Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-production.txt -r requirements-test.txt
```

Run the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn course_recommender.api:app --host 127.0.0.1 --port 8001
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Run syntax checks:

```powershell
.\.venv\Scripts\python.exe -m py_compile course_recommender\api.py course_recommender\batch_export.py course_recommender\cre_contract.py course_recommender\config.py course_recommender\export_store.py course_recommender\security.py scripts\generate_export.py scripts\sign_request.py
```

## Local Frontend Development

```powershell
Set-Location frontend
npm install
npm run dev
```

Build before committing frontend changes:

```powershell
npm run build
```

The main files are:

```text
frontend/src/App.tsx        Main UI
frontend/src/apiClient.ts   Backend client
frontend/src/types.ts       API response types
frontend/src/styles.css     Dark-mode styling
```

## Data And Artifact Rules

Required data files live in `data/`:

```text
data/users.csv
data/courses.csv
data/interactions.csv
data/course_alias_map.csv
```

Generated artifacts live in `course_recommender_artifacts_final/`:

```text
course_recommender_artifacts_final/model/
course_recommender_artifacts_final/config/
course_recommender_artifacts_final/tables/
course_recommender_artifacts_final/export/
course_recommender_artifacts_final/artifact_manifest.csv
```

Rules:

- Keep `user_id` as a string.
- Keep `canonical_course_id` as a string.
- Do not use course names as primary identifiers.
- Do not expose Moodle internal IDs from this service.
- Keep raw datasets and generated artifacts out of git unless the team explicitly decides otherwise.

## Deploy To A VPS

The simplest VPS deployment is Docker Compose behind a reverse proxy such as Nginx or Caddy.

Recommended server baseline:

- Ubuntu 22.04 or 24.04 LTS.
- 2 CPU cores minimum.
- 4 GB RAM minimum for light testing.
- More RAM if model loading or export generation grows.
- Docker Engine and Docker Compose plugin installed.
- A domain name pointing to the VPS.

### 1. Prepare The Server

Install Docker on the VPS:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Allow your user to run Docker:

```bash
sudo usermod -aG docker $USER
```

Log out and back in after changing the group.

### 2. Upload The Project

Clone the repository:

```bash
git clone <your-repository-url> MLmodelWeb
cd MLmodelWeb
```

Upload or copy these runtime folders if they are not stored in git:

```text
data/
course_recommender_artifacts_final/
```

For a small project, `scp` is enough:

```bash
scp -r data course_recommender_artifacts_final user@your-vps-ip:/home/user/MLmodelWeb/
```

### 3. Configure Production Env

Create `.env` from the production template:

```bash
cp .env.production.example .env
nano .env
```

Generate an admin password hash. If Python 3 is available on the VPS:

```bash
python3 scripts/hash_admin_password.py
```

If you prefer Docker only, build the backend image first and run the helper:

```bash
docker build -t cre-ml-service:pre-mvp .
docker run --rm -it cre-ml-service:pre-mvp python scripts/hash_admin_password.py
```

Put the printed hash into `CRE_ML_ADMIN_PASSWORD_HASH`. Because PBKDF2 hashes contain `$`, wrap the value in single quotes in `.env`. Use strong random values for all secrets:

```text
CRE_ML_API_KEY=<long-random-api-key>
CRE_ML_HMAC_SECRET=<long-random-hmac-secret>
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
CRE_ML_SESSION_SECRET=<long-random-session-secret>
CRE_ML_REQUIRE_AUTH=true
CRE_ML_ENABLE_TEST_UI=true
CRE_ML_TEST_UI_ORIGINS=https://cre-admin.your-domain.example
CRE_ML_SESSION_COOKIE_SECURE=true
CRE_UI_API_BASE_URL=https://cre-api.your-domain.example
```

For public deployment, do not use placeholder secrets and do not use plaintext admin passwords.

### 4. Adjust Port Binding

The local Compose file binds services to `127.0.0.1`, which is correct when using a reverse proxy on the same VPS.

Keep the backend private:

```text
127.0.0.1:8001:8001
```

The frontend container serves a production static build through Nginx and binds privately:

```text
127.0.0.1:5173:80
```

Expose both ports only through an HTTPS reverse proxy.

### 5. Start The Stack

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f cre-ml-service
```

Check locally on the VPS:

```bash
curl http://127.0.0.1:8001/health
```

### 6. Add Reverse Proxy

Example Nginx backend API proxy:

```nginx
server {
    listen 80;
    server_name ml-api.your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable TLS with Certbot:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d ml-api.your-domain.example
```

After TLS is active, the LMS should call:

```text
https://ml-api.your-domain.example/recommendations/export
```

### 7. Deploy The Admin Console On VPS

Only deploy the admin console when needed. If exposed publicly, protect it with HTTPS, strong admin credentials, VPN or firewall allowlist where possible, and short-lived session settings.

Example Nginx proxy for the Docker frontend:

```nginx
server {
    listen 80;
    server_name ml-ui.your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The browser UI calls the backend URL baked into the frontend image at build time:

```text
CRE_UI_API_BASE_URL=https://cre-api.your-domain.example
```

When using the `/ui/api/*` bridge remotely, the backend must have:

```text
CRE_ML_ENABLE_TEST_UI=true
CRE_ML_TEST_UI_ORIGINS=https://ml-ui.your-domain.example
CRE_ML_ADMIN_USERNAME=admin
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
CRE_ML_SESSION_SECRET=<long-random-session-secret>
CRE_ML_SESSION_COOKIE_SECURE=true
```

### 8. VPS Smoke Test

Run these checks after deployment:

```bash
curl https://ml-api.your-domain.example/health
docker compose exec -T cre-ml-service python -m pytest tests -q
docker compose logs --tail=100 cre-ml-service
```

For signed endpoint testing, generate headers inside the container:

```bash
docker compose exec -T cre-ml-service python scripts/sign_request.py /recommendations/export --query "limit=10"
```

Then call the HTTPS endpoint with the printed headers.

## Production Notes

- Keep `CRE_ML_REQUIRE_AUTH=true`.
- Keep `CRE_ML_ENABLE_TEST_UI=false` unless explicitly testing.
- Rotate `CRE_ML_API_KEY` and `CRE_ML_HMAC_SECRET` if they are shared accidentally.
- Bind Docker ports to `127.0.0.1` and expose public traffic through HTTPS reverse proxy.
- Back up `course_recommender_artifacts_final/` and the exact dataset used to generate them.
- Regenerate recommendation exports as part of model update deployment.
- Watch container memory usage after model or dataset changes.
- Do not use the Vite dev server as the final public frontend for a production product.

## Useful Commands

```powershell
# Start everything
docker compose up --build -d

# See running services
docker compose ps

# Backend logs
docker compose logs -f cre-ml-service

# Frontend logs
docker compose logs -f cre-ml-ui

# Backend tests
docker compose exec -T cre-ml-service python -m pytest tests -q

# Frontend build
docker compose exec -T cre-ml-ui npm run build

# Generate export
docker compose run --rm cre-ml-service python scripts/generate_export.py --top-k 20

# Stop everything
docker compose down
```
