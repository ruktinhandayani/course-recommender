# CRE API Contract

## 1. Purpose

This contract defines communication between Moodle `local_courserecommender` and the external ML Recommendation Service.

The ML service returns recommendation candidates. Moodle performs final mapping, validation, caching, and display.

## 2. API Design Decisions

```text
- main sync uses paginated bulk export
- page size is 1000 rows
- user-level endpoint is optional and debug-only
- ML service does not know Moodle internal ids
- all IDs are serialized as strings
- response includes model_version and generated_at
- Moodle preserves original ML rank
```

## 3. Authentication and Signing

MVP security uses:

```text
- API key or bearer token
- HMAC-SHA256 signature
- timestamp anti-replay
- request id for traceability
```

Required request headers:

```http
Authorization: Bearer {api_key}
X-Request-Id: sync-20260709-000001
X-Timestamp: 1783558800
X-Signature: {hex_hmac_sha256}
Accept: application/json
```

Recommended signature canonical string:

```text
HTTP_METHOD + "\n" +
PATH + "\n" +
CANONICAL_QUERY_STRING + "\n" +
SHA256_HEX(REQUEST_BODY) + "\n" +
X_TIMESTAMP + "\n" +
X_REQUEST_ID
```

For GET requests, request body is empty:

```text
SHA256_HEX("")
```

Server validation:

```text
- reject missing API key
- reject invalid API key
- reject missing signature
- reject invalid signature
- reject timestamp older than 60 seconds, or configured tolerance
- use constant-time signature comparison
```

## 4. Main Endpoint: Paginated Export

```http
GET /recommendations/export?model_version=latest&cursor={cursor}&limit=1000
```

Query parameters:

| Name | Required | Description |
|---|---|---|
| `model_version` | no | `latest` or exact model version |
| `cursor` | no | opaque pagination cursor |
| `limit` | no | max rows per page, default 1000, max 1000 |
| `mode` | no | `normal` or `test`, for fixture testing only |

## 5. Export Success Response

```json
{
  "request_id": "sync-20260709-000001",
  "model_version": "cre-lstm-attention-h2-seed42-fullmask-v1",
  "generated_at": "2026-07-09T00:15:00+07:00",
  "page": {
    "limit": 1000,
    "next_cursor": "eyJvZmZzZXQiOjEwMDB9",
    "has_more": true
  },
  "recommendations": [
    {
      "user_id": "000123451",
      "canonical_course_id": "183",
      "rank": 1,
      "score": 0.9231,
      "reason_code": null
    },
    {
      "user_id": "000123451",
      "canonical_course_id": "52",
      "rank": 2,
      "score": 0.8814,
      "reason_code": null
    }
  ]
}
```

Required response fields:

```text
request_id
model_version
generated_at
page.limit
page.has_more
recommendations[].user_id
recommendations[].canonical_course_id
recommendations[].rank
recommendations[].score
```

Optional response fields:

```text
page.next_cursor
recommendations[].reason_code
```

## 6. Pagination Rules

Moodle sync loop:

```text
1. Call export endpoint without cursor.
2. Process returned recommendations.
3. If has_more = true, call endpoint again with next_cursor.
4. Stop when has_more = false.
5. Only activate new recommendations after all pages succeed.
```

ML service rules:

```text
- limit must not exceed 1000
- cursor is opaque to Moodle
- response order should be stable for the same model_version
- repeated calls with the same cursor should return the same page during a sync window
```

## 7. Optional Debug Endpoint

```http
GET /recommendations/user/{user_id}?model_version=latest
```

Purpose:

```text
- manual refresh debugging
- development verification
- not the main scheduled sync path
```

Success response:

```json
{
  "request_id": "debug-20260709-000123451",
  "user_id": "000123451",
  "model_version": "cre-lstm-attention-h2-seed42-fullmask-v1",
  "generated_at": "2026-07-09T00:15:00+07:00",
  "recommendations": [
    {
      "canonical_course_id": "183",
      "rank": 1,
      "score": 0.9231,
      "reason_code": null
    }
  ]
}
```

## 8. Error Response

```json
{
  "request_id": "sync-20260709-000001",
  "error": {
    "code": "INVALID_SIGNATURE",
    "message": "Request signature is invalid."
  }
}
```

Expected HTTP statuses:

| Status | Meaning |
|---:|---|
| 200 | success |
| 400 | invalid request |
| 401 | missing/invalid API key |
| 403 | invalid signature or expired timestamp |
| 404 | debug user not found |
| 422 | invalid model_version or invalid pagination cursor |
| 500 | internal ML service error |
| 503 | model/export not ready |

Expected error codes:

```text
INVALID_API_KEY
INVALID_SIGNATURE
EXPIRED_TIMESTAMP
INVALID_CURSOR
INVALID_LIMIT
MODEL_NOT_READY
MODEL_VERSION_NOT_FOUND
USER_NOT_FOUND
EXPORT_NOT_READY
INTERNAL_ERROR
```

## 9. Data Type Rules

Use strings for identifiers:

```text
user_id: string
canonical_course_id: string
model_version: string
```

Use numeric types for ranking:

```text
rank: positive integer
score: decimal number
```

Moodle should reject or skip rows with:

```text
- missing user_id
- missing canonical_course_id
- non-positive rank
- non-numeric score
- duplicate user_id + canonical_course_id within the same sync run
```

## 10. Test Fixture Mode

The ML service may expose deterministic fixture output:

```http
GET /recommendations/export?mode=test&limit=1000
```

Use this only for evaluation fixtures.

Fixture rows should be marked in Moodle sync run:

```text
run_type = fixture
```

Fixture rows should not be mixed with normal production-like sync results.

## 11. Logging Policy

Moodle should log:

```text
- request_id
- sync_run_id
- HTTP status
- response status
- latency
- model_version
- counts received/mapped/displayable/skipped
- error code
```

Do not log:

```text
- raw request body containing sensitive identifiers
- API key
- HMAC secret
- full stack traces with secrets
```

Operational logs should mask user ID where possible.

Functional data tables may store `user_id` because the integration requires it.
