# Course Recommender Backend Integration Contract

This repository exposes the recommender in two ways:

- as an importable Python package for batch generation and direct integration
- as a FastAPI service that serves pre-generated recommendation exports and the standalone admin console API

The production API serves precomputed recommendation rows from
`course_recommender_artifacts_final/export/recommendations.csv`. The TensorFlow model
is not run on every user lookup in the standalone console.

## Runtime files

The final experiment snapshot contains these runtime files:

- `course_recommender_artifacts_final/model/cre-lstm-attention-h2-seed42-fullmask-v1.keras`
- `course_recommender_artifacts_final/config/experiment_config.json`
- `course_recommender_artifacts_final/config/evaluation_final.json`
- `course_recommender_artifacts_final/config/encoder_mappings.pkl`
- `course_recommender_artifacts_final/config/certificate_count_scaler.pkl`
- `course_recommender_artifacts_final/tables/course_catalog.csv`
- `course_recommender_artifacts_final/tables/course_popularity_train_df.csv`
- `course_recommender_artifacts_final/artifact_manifest.csv`

## Backend usage

Direct Python usage is still available for batch jobs or custom backends:

```python
import pandas as pd
from course_recommender import load_recommender

recommender = load_recommender("course_recommender_artifacts_final")

history_df = pd.DataFrame([
    {
        "user_id": "123",
        "canonical_course_id": "COURSE-001",
        "sort_timestamp": "2026-01-01T00:00:00",
    }
])

response = recommender.recommend(
    user_id="123",
    user_history_df=history_df,
    top_n=10,
)
```

`response` is JSON-serializable and contains:

- `user_id`
- `recommendations`: ranked course rows
- `metadata`: fallback reason, history counts, catalog check status, and errors

## Input history contract

Minimum accepted columns:

- `canonical_course_id`

Recommended columns:

- `user_id`
- `sort_timestamp`, `sort_interaction_id`, or `sort_row_order`

Optional columns if the backend already has encoded/enriched history:

- `course_encoded`
- `kompetensi`
- `level`
- `certificate_count_train`
- `course_has_certificate_train`

If optional course metadata is missing, the service enriches it from
`course_catalog.csv`.

## Operational notes

- Load `CourseRecommenderService` once per process, not once per request.
- For the current FastAPI runtime, normal user/export lookups read from the generated export store.
- Regenerate the export through `scripts/generate_export.py --top-k 20` or the admin console Refresh page when model artifacts or input data change. This runs batch inference; it does not retrain the model.
- Keep all artifact files from the same notebook run together.
- Use the `metadata.fallback_reason` field for monitoring.
- Fallback recommendations are popularity-based and exclude known user history
  when the history is usable.
- Retrain and republish all artifacts together when the course catalog changes.

## Standalone Console API

The admin console uses `/ui/api/*` routes:

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

These routes require an admin session cookie and should only be exposed behind
HTTPS with strong credentials.

The LMS-facing service-to-service routes remain HMAC protected:

```text
GET /recommendations/export
GET /recommendations/user/{user_id}
```
