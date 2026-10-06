# CRE Implementation Task List

## 1. Implementation Principle

Build the smallest complete system that proves the integration architecture.

Do not add:

```text
- production queue system
- public internet deployment
- manager dashboard
- complex analytics dashboard
- LLM explanations
- full mTLS/VPC implementation for MVP
```

Do build:

```text
- working local plugin
- working block plugin
- ML export service wrapper
- seed scripts
- atomic sync
- cache display
- logs and evaluation metrics
```

## 2. Phase 1: Moodle Plugin Skeletons

### 2.1 `local_courserecommender`

Tasks:

```text
- create plugin skeleton
- version.php
- db/install.xml
- db/access.php
- settings.php
- classes/privacy/provider.php
- classes/task/sync_recommendations.php
- cli scripts directory
```

Capabilities:

```text
local/courserecommender:viewdiagnostics
local/courserecommender:runsync
local/courserecommender:exportlogs
```

For MVP, assign these to site admins only.

### 2.2 `block_courserecommender`

Tasks:

```text
- create block skeleton
- render top-3 active cached recommendations
- show empty state
- show stale state
- add simple course links
- implement null privacy provider if it stores no data
```

## 3. Phase 2: Database Tables

Create tables:

```text
local_cr_users
local_cr_courses
local_cr_course_alias
local_cr_interactions
local_cr_course_map
local_cr_sync_runs
local_cr_recommendations
local_cr_rec_skip
local_cr_eval_results
```

Indexes:

```text
- local_cr_users.user_id unique
- local_cr_courses.canonical_course_id unique
- local_cr_course_map.canonical_course_id unique
- local_cr_recommendations(user_id, is_active)
- local_cr_recommendations(sync_run_id)
- local_cr_rec_skip(sync_run_id)
- local_cr_rec_skip(skip_reason)
```

## 4. Phase 3: Data Seed CLI

Create:

```text
local/courserecommender/cli/seed_dataset.php
local/courserecommender/cli/seed_moodle_demo.php
local/courserecommender/cli/setup_demo.php
```

### 4.1 `seed_dataset.php`

Input:

```text
--data-dir=/path/to/data-cleaned
```

Imports:

```text
users.csv -> local_cr_users
courses.csv -> local_cr_courses
course_alias_map.csv -> local_cr_course_alias
interactions.csv -> local_cr_interactions
```

Requirements:

```text
- preserve user_id leading zeros
- store canonical_course_id as string
- upsert/idempotent import
- print import summary
```

### 4.2 `seed_moodle_demo.php`

Creates Moodle demo state:

```text
- selected Moodle users
- Moodle courses
- course categories if needed
- canonical_course_id -> moodle_courseid mapping
- enrolment fixtures
- completion fixtures
- hidden course fixtures
```

Recommended defaults:

```text
--users=300
--courses=all
```

User selection:

```text
- active users
- medium users
- sparse users
- certified users
- edge-case users
```

### 4.3 `setup_demo.php`

Wrapper script:

```text
1. seed_dataset.php
2. seed_moodle_demo.php
3. optional sync_recommendations.php
4. print summary
```

## 5. Phase 4: ML Recommendation Service Wrapper

Build or expose:

```text
GET /recommendations/export
GET /recommendations/user/{user_id}
```

ML service can load:

```text
- generated recommendations CSV
- database table
- model batch output
```

Required behavior:

```text
- paginated response
- limit max 1000
- stable ordering
- model_version included
- generated_at included
- HMAC/API key validation
```

## 6. Phase 5: Moodle API Client

Create service class:

```text
local_courserecommender\service\ml_client
```

Responsibilities:

```text
- build signed request
- call export endpoint
- handle pagination
- enforce timeout
- parse JSON
- validate response shape
- return typed result objects/arrays
```

Do not log secrets or raw payloads.

## 7. Phase 6: Sync Service

Create service class:

```text
local_courserecommender\service\sync_service
```

Responsibilities:

```text
- create sync run
- fetch all pages
- validate rows
- map courses
- check Moodle visibility/completion/enrolment
- insert pending recommendations
- insert skip logs
- activate new rows only after complete success
- keep old active rows on failure
- update sync run metrics
```

Expected skip reasons:

```text
user_not_found
course_not_found
unmapped_course
hidden_course
completed_course
already_enrolled
duplicate_recommendation
invalid_payload
invalid_score
invalid_rank
```

## 8. Phase 7: Scheduled Task and CLI Sync

Create:

```text
classes/task/sync_recommendations.php
cli/sync_recommendations.php
```

Both call the same `sync_service`.

CLI options:

```text
--mode=normal|fixture
--model-version=latest
--limit=1000
```

Scheduled task:

```text
- runs daily after ML batch
- can be triggered by Moodle cron
```

## 9. Phase 8: Admin Diagnostics Page

Create:

```text
local/courserecommender/diagnostics.php
```

Protect with:

```text
require_login()
require_capability('local/courserecommender:viewdiagnostics', context_system::instance())
```

Show:

```text
- last sync status
- model_version
- active recommendation count
- stale recommendation count
- total received/mapped/displayable/skipped
- skip reason counts
- API latency
- sync duration
```

Actions:

```text
- test ML connection
- run manual sync
- run fixture sync
- export evaluation CSV
```

Actions should call service classes. Do not put business logic in page scripts.

## 10. Phase 9: Dashboard Block

Dashboard behavior:

```text
- find current user's local_cr_users row by moodle_userid
- load active recommendations
- sort by original_rank
- display top-3
- show match score plainly
- link to course view page
- show empty state if none
- show stale indicator if cache older than 24 hours
```

No ML API calls.

## 11. Phase 10: Evaluation Runner

Create:

```text
cli/run_evaluation.php
```

Responsibilities:

```text
- run fixture sync
- verify expected outcomes
- write local_cr_eval_results
- print metrics
- export CSV summary
```

Test fixture source:

```text
recommendation_test_fixtures.csv
```

or:

```text
GET /recommendations/export?mode=test
```

## 12. Phase 11: Basic Privacy Provider

For `local_courserecommender`:

```text
- declare stored user-related data
- export a user's recommendation data
- delete/anonymize a user's recommendation data
```

For `block_courserecommender`:

```text
- null provider if it stores no data directly
```

## 13. Definition of Done

The MVP is done when:

```text
1. plugins install without Moodle core modification
2. dataset can be seeded automatically
3. Moodle demo data can be seeded automatically
4. ML export API returns paginated recommendations
5. Moodle sync is atomic and idempotent
6. invalid candidates are skipped and logged
7. dashboard displays top-3 cached recommendations
8. stale/empty states work
9. ML failure does not break dashboard
10. evaluation metrics can be exported
```
