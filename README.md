# CRE ML Recommendation Service

This repository is the ML service and standalone admin console repo for CRE, Course Recommendation for Employees. It owns the recommendation model artifacts, batch recommendation export, secured HTTP API, and a Dockerized React admin console for inspecting and refreshing recommendations.

The service does not render LMS pages and does not use Moodle internal course IDs. It only exchanges integration-safe identifiers:

- `user_id`
- `canonical_course_id`

## Current Project Status

This repo is in the **Pre-MVP ML service + standalone admin console** stage.

Implemented:

- TensorFlow/Keras recommender loading from saved artifacts.
- Latest notebook artifact set with 4,553 temporal test samples.
- Live per-user inference when a prepared batch export is not available.
- Automatic ID resolution that preserves leading zeroes.
- One-ID demo view containing employee name, pre-target course history,
  attention weights, Top-10 recommendations, and held-out next-course check.
- Batch top-K recommendation export.
- Paginated FastAPI export endpoint.
- Optional per-user recommendation debug endpoint.
- Bearer API key authentication.
- HMAC-SHA256 request signing.
- Timestamp anti-replay validation.
- Deterministic fixture export for simulator tests.
- Standalone admin console with login, overview, user search, export review, evaluation, refresh, and raw-response pages.
- Admin-only `/ui/api/*` endpoints protected by an HTTP-only session cookie.
- Refresh job endpoint that can regenerate the recommendation export and stream/poll computing logs.
- Evaluation summary endpoint backed by generated artifact tables.
- Pytest coverage for API contract, pagination, fixture mode, and security behavior.
- Cleaned project folder structure and project README.

Latest offline temporal evaluation:

```text
Test samples : 4,553
Hit@1        : 59.98%
Hit@5        : 83.86%
Hit@10       : 92.73%
MRR@10       : 70.11%
NDCG@10      : 75.52%
Coverage@10  : 100%
```

Recommended sidang demo ID: `002156217`. The source ID resolves to Angger Eka
Samekta, contains ten pre-target course records without `Course senin`, and the
held-out next course `Pengoperasian Vibrating Screen` is ranked first.

For demonstrating the complete learning-progress panel, use `002156394`
(Zuhdi Muafa Fattah). It has 32 tracked courses, 27 completed courses, an
84.38% completion rate, an average score of 74.93, eight certificates, no
`Course senin` in its model history, and its held-out next course is ranked
first.

## Project Structure

```text
course_recommender/              Python package: model service, API, auth, security, export store
scripts/                         CLI helpers for export generation and request signing
tests/                           Pytest tests for API and export behavior
data/                            Local CSV dataset inputs, ignored by git
course_recommender_artifacts_final/ Generated final-run model/config/tables/export artifacts, ignored by git
notebooks/research/              Original research/training notebook
frontend/                        React + TypeScript + Vite admin console
docs/                            Architecture, API contract, roadmap, and service notes
reports/figures/                 Generated report figures, ignored by git
```

## What This Service Provides

- Loads the final trained recommender artifacts from `course_recommender_artifacts_final/`.
- Generates top-K recommendation candidates for users.
- Serves recommendation candidates through a stable API contract.
- Provides a fixture mode for integration and failure-path tests.
- Provides an admin console for local/research inspection and export refresh.
- Keeps final LMS display decisions outside the ML service.

The LMS side is responsible for:

- mapping `canonical_course_id` to local LMS or Moodle course IDs
- filtering hidden, completed, already-enrolled, or unmapped courses
- caching recommendations
- rendering dashboard recommendations

## Environment Setup

Use Python 3.11 or 3.12.

Docker is the preferred runtime path for this repo because it avoids local Python and TensorFlow installation issues.

Create or repair the local virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Install runtime dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-production.txt
```

Install notebook/research dependencies when working with the research notebook:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
```

Copy `.env.example` to `.env` and set real secrets before connecting another service. For admin login, use a password hash instead of a plaintext password:

```text
CRE_ML_API_KEY=...
CRE_ML_HMAC_SECRET=...
CRE_ML_ADMIN_PASSWORD_HASH='pbkdf2_sha256$...'
CRE_ML_SESSION_SECRET=...
CRE_ML_DATA_DIR=data
```

Generate an admin password hash with:

```powershell
docker run --rm -it cre-ml-service:pre-mvp python scripts/hash_admin_password.py
```

Do not commit real API keys or HMAC secrets.

## Docker Setup

Create `.env` first by copying the template, then replace every placeholder:

```powershell
Copy-Item .env.example .env
```

The local template can be used immediately with `admin` / `admin`. This is
only for a local sidang demo. Change `CRE_ML_ADMIN_PASSWORD` before presenting
or sharing the project.

For a deployment, remove the plaintext password and put only a PBKDF2 hash in
`.env`:

```powershell
docker build -t cre-ml-service:pre-mvp .
docker run --rm -it cre-ml-service:pre-mvp python scripts/hash_admin_password.py
```

Set the printed value as `CRE_ML_ADMIN_PASSWORD_HASH`. Because PBKDF2 hashes contain `$`, wrap the value in single quotes in `.env`.

Build the images:

```powershell
$env:DOCKER_CONFIG="$PWD\.docker-config"
docker compose build
```

Run the full stack:

```powershell
$env:DOCKER_CONFIG="$PWD\.docker-config"
docker compose up --build -d
```

The Compose services bind locally:

```text
Admin console: http://127.0.0.1:5173
Backend API:   http://127.0.0.1:8001
```

Admin login:

```text
username: admin
password: admin (default local template)
```

For VPS deployment, remove `CRE_ML_ADMIN_PASSWORD`, generate a new password on
the server, and store only `CRE_ML_ADMIN_PASSWORD_HASH`.

Run tests inside Docker:

```powershell
$env:DOCKER_CONFIG="$PWD\.docker-config"
docker compose run --rm cre-ml-service python -m pytest tests -q
```

Generate recommendation export inside Docker:

```powershell
$env:DOCKER_CONFIG="$PWD\.docker-config"
docker compose run --rm cre-ml-service python scripts/generate_export.py --top-k 20
```

The project-local `DOCKER_CONFIG` avoids the known Windows warning where Docker cannot read `C:\Users\xenpul\.docker\config.json`.

## Required Data Files

The cleaned dataset belongs in `data/`:

```text
data/users.csv
data/courses.csv
data/interactions.csv
data/course_alias_map.csv
data/learning_progress_summary.csv
data/learning_progress_detail.csv
```

Important data rules:

- Keep `user_id` as a string.
- Keep `canonical_course_id` as a string.
- Do not use course names as primary identifiers.
- Do not expose Moodle internal IDs from the ML service.

The two learning-progress files are website support data. They do not become
model inputs and do not change the recommendation ranking. Rebuild them from
the original LMS enrollment-status, score, and certificate workbooks with
`scripts/build_learning_progress.py`.

## Generated Artifacts

The final model and export artifacts belong in `course_recommender_artifacts_final/`:

```text
course_recommender_artifacts_final/model/
course_recommender_artifacts_final/config/
course_recommender_artifacts_final/tables/
course_recommender_artifacts_final/export/
course_recommender_artifacts_final/artifact_manifest.csv
```

The active model version is `cre-lstm-attention-h2-seed42-fullmask-v1`.

The latest notebook ZIP intentionally does not include a batch `export/`
directory. This is supported: User Search performs live model inference
automatically. Use Refresh or `scripts/generate_export.py` only when a batch
export is needed for Export Review.

The service supports batch recommendation generation for the available user population. The active dashboard export may be a limited demonstration subset configured through Max Users; its actual mode, user count, Top-K, and row count are reported by `recommendation_export_manifest.json` and do not alter offline temporal evaluation results.

The export manifest is the source of truth for the current export scope. A complete Top-20 export is expected to contain `9,598` users and `191,960` recommendation rows; those counts are valid only after a full export completes successfully. A limited test export must not be presented as the final export.

Regenerate the export whenever model artifacts or input CSV data change. This performs batch inference with the active trained model; it does not retrain the model.

## Generate Recommendation Export

The API serves pre-generated recommendation candidates. Generate the export after model artifacts and input data are ready:

```powershell
 .\.venv\Scripts\python.exe scripts\generate_export.py --top-k 20
```

Generated files:

```text
course_recommender_artifacts_final/export/recommendations.csv
course_recommender_artifacts_final/export/recommendations_fixture.csv
course_recommender_artifacts_final/export/recommendation_export_manifest.json
```

The admin console can also trigger `Regenerate Recommendations` from the `Refresh` page. Leave Max users empty and use Top-K `20` to generate the full export. That action is admin-only, runs the same batch export flow, and does not retrain the model.

## Run the API

Local Python:

```powershell
.\.venv\Scripts\python.exe -m uvicorn course_recommender.api:app --host 127.0.0.1 --port 8001
```

Check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

## Standalone Admin Console

The Dockerized console is available at:

```text
http://127.0.0.1:5173
```

Pages:

- `Overview`: service health, artifact status, export count, evaluation metric cards.
- `User Search`: per-user lookup of ranked results already present in the active recommendation export; it does not run live inference.
- `Export Review`: paginated recommendation export browser.
- `Evaluation`: artifact-backed evaluation tables.
- `Refresh`: regenerate the export and watch live computing logs.
- `Raw Response`: inspect exact JSON payloads.

The console uses `/ui/api/*` endpoints and requires an admin session. The service-to-service endpoints remain HMAC protected.

## Signed Request Flow

Recommendation endpoints require:

```http
Authorization: Bearer {api_key}
X-Request-Id: {request_id}
X-Timestamp: {unix_timestamp}
X-Signature: {hmac_sha256}
```

Generate headers for manual testing:

```powershell
.\.venv\Scripts\python.exe scripts\sign_request.py /recommendations/export --query "limit=10"
```

The signature uses a canonical query string sorted by parameter name. Use the printed `Canonical-Query` value when testing requests with multiple query parameters.

## API Contract Summary

Health endpoint:

```http
GET /health
```

Main sync endpoint:

```http
GET /recommendations/export?model_version=latest&cursor={cursor}&limit=1000
```

Fixture mode for simulator tests:

```http
GET /recommendations/export?mode=test&limit=1000
```

Per-user debug endpoint:

```http
GET /recommendations/user/{user_id}?model_version=latest
```

Example response shape:

```json
{
  "request_id": "sync-001",
  "model_version": "cre-lstm-attention-h2-seed42-fullmask-v1",
  "generated_at": "2026-07-12T21:49:48+07:00",
  "page": {
    "limit": 1000,
    "next_cursor": null,
    "has_more": false
  },
  "recommendations": [
    {
      "user_id": "2156220",
      "canonical_course_id": "66",
      "rank": 1,
      "score": 0.6189,
      "reason_code": null
    }
  ]
}
```

## Verification

Run syntax checks:

```powershell
.\.venv\Scripts\python.exe -m py_compile course_recommender\api.py course_recommender\batch_export.py course_recommender\cre_contract.py course_recommender\config.py course_recommender\export_store.py course_recommender\security.py scripts\generate_export.py scripts\sign_request.py
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected coverage:

- paginated export store
- invalid cursor handling
- contract-compatible API responses
- fixture mode
- user debug endpoint
- admin login/session checks
- protected UI endpoints
- evaluation endpoint shape
- missing and invalid security headers

## Next Project Step

After the Dockerized service and admin console are stable, the next project step is the **Pre-MVP PHP LMS simulator**.

The simulator should prove:

- signed PHP client can call the ML export API
- paginated sync works
- recommendations can be mapped and cached
- invalid or unmapped rows are skipped and logged
- dashboard can display top-3 cached recommendations
- failed sync does not wipe old active recommendations

Only after this Pre-MVP simulator works should the project move to the Moodle MVP.

## Related Docs

- [Developer guide](docs/DEVELOPER_GUIDE.md)
- [Project handover](docs/HANDOVER.md)
- [Pre-MVP ML service notes](docs/ML_SERVICE_PRE_MVP.md)
- [API contract](docs/03_api_contract.md)
- [Architecture design](docs/01_final_architecture_design.md)
- [Implementation task list](docs/04_implementation_task_list.md)
- [Evaluation plan](docs/05_evaluation_plan.md)
- [Security deployment](docs/SECURITY_DEPLOYMENT.md)
- [Phase roadmap](docs/phase_roadmap/implementation_plan.md)
- [Environment notes](docs/setup/ENVIRONMENT.md)
