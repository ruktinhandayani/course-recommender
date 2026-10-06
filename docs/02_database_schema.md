# CRE Database Schema

## 1. Schema Goals

The schema supports:

```text
- cleaned dataset import
- Moodle identity mapping
- canonical course mapping
- recommendation cache
- atomic sync
- skip reason logging
- evaluation result logging
- basic privacy/export support
```

All table names use the `local_cr_` prefix for the `local_courserecommender` plugin.

## 2. Table Overview

Minimum tables:

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

Optional table:

```text
local_cr_seed_runs
```

## 3. Entity Relationship Overview

```text
local_cr_users.user_id
    -> local_cr_interactions.user_id
    -> local_cr_recommendations.user_id
    -> local_cr_rec_skip.user_id

local_cr_courses.canonical_course_id
    -> local_cr_interactions.canonical_course_id
    -> local_cr_course_alias.canonical_course_id
    -> local_cr_course_map.canonical_course_id
    -> local_cr_recommendations.canonical_course_id
    -> local_cr_rec_skip.canonical_course_id

local_cr_course_map.moodle_courseid
    -> mdl_course.id

local_cr_users.moodle_userid
    -> mdl_user.id

local_cr_sync_runs.id
    -> local_cr_recommendations.sync_run_id
    -> local_cr_rec_skip.sync_run_id
    -> local_cr_eval_results.sync_run_id
```

## 4. DBML Draft

Paste this into dbdiagram.io for visualization.

```dbml
Table local_cr_users {
  id bigint [pk, increment]
  user_id varchar(20) [unique, not null, note: 'Employee/dataset user id, keep as string']
  moodle_userid bigint [note: 'FK to mdl_user.id, nullable until Moodle user is seeded']
  full_name varchar(255)
  source_system varchar(50)
  created_at bigint
  updated_at bigint
}

Table local_cr_courses {
  id bigint [pk, increment]
  canonical_course_id varchar(50) [unique, not null]
  course_name varchar(255) [not null]
  description text
  level varchar(100)
  kompetensi varchar(255)
  created_at bigint
  updated_at bigint
}

Table local_cr_course_alias {
  id bigint [pk, increment]
  legacy_course_id varchar(50) [not null]
  canonical_course_id varchar(50) [not null, ref: > local_cr_courses.canonical_course_id]
  created_at bigint

  indexes {
    (legacy_course_id) [unique]
    (canonical_course_id)
  }
}

Table local_cr_interactions {
  id bigint [pk, increment]
  interaction_id bigint [unique, not null]
  user_id varchar(20) [not null, ref: > local_cr_users.user_id]
  canonical_course_id varchar(50) [not null, ref: > local_cr_courses.canonical_course_id]
  interaction_type varchar(20) [not null, note: 'enrolled | certified']
  event_timestamp bigint [note: 'Unix timestamp, nullable for certified rows']
  source_system varchar(80)
  created_at bigint

  indexes {
    (user_id)
    (canonical_course_id)
    (user_id, canonical_course_id)
  }
}

Table local_cr_course_map {
  id bigint [pk, increment]
  canonical_course_id varchar(50) [unique, not null, ref: > local_cr_courses.canonical_course_id]
  moodle_courseid bigint [not null, note: 'FK to mdl_course.id']
  mapping_source varchar(50) [note: 'seed | manual | script']
  created_at bigint
  updated_at bigint

  indexes {
    (moodle_courseid)
  }
}

Table local_cr_sync_runs {
  id bigint [pk, increment]
  run_uuid varchar(64) [unique, not null]
  run_type varchar(30) [not null, note: 'scheduled | manual | fixture | cli']
  status varchar(30) [not null, note: 'running | success | failed | partial']
  model_version varchar(100)
  requested_cursor varchar(255)
  started_at bigint
  finished_at bigint
  duration_ms bigint
  api_latency_ms bigint
  total_pages int
  total_received bigint
  total_mapped bigint
  total_displayable bigint
  total_skipped bigint
  activated_count bigint
  error_code varchar(80)
  error_message text
  created_by bigint [note: 'Moodle user id that triggered manual run, nullable']

  indexes {
    (status)
    (model_version)
    (started_at)
  }
}

Table local_cr_recommendations {
  id bigint [pk, increment]
  sync_run_id bigint [not null, ref: > local_cr_sync_runs.id]
  user_id varchar(20) [not null, ref: > local_cr_users.user_id]
  moodle_userid bigint
  canonical_course_id varchar(50) [not null, ref: > local_cr_courses.canonical_course_id]
  moodle_courseid bigint [not null]
  original_rank int [not null]
  display_rank int
  score decimal(12, 8)
  reason_code varchar(100)
  model_version varchar(100)
  generated_at bigint
  is_active boolean [not null, default: false]
  activated_at bigint
  created_at bigint

  indexes {
    (user_id, is_active)
    (moodle_userid, is_active)
    (canonical_course_id)
    (sync_run_id)
    (model_version)
    (user_id, canonical_course_id, sync_run_id) [unique]
  }
}

Table local_cr_rec_skip {
  id bigint [pk, increment]
  sync_run_id bigint [not null, ref: > local_cr_sync_runs.id]
  user_id varchar(20)
  canonical_course_id varchar(50)
  original_rank int
  score decimal(12, 8)
  skip_reason varchar(80) [not null]
  detail text
  created_at bigint

  indexes {
    (sync_run_id)
    (skip_reason)
    (user_id)
    (canonical_course_id)
  }
}

Table local_cr_eval_results {
  id bigint [pk, increment]
  sync_run_id bigint [ref: > local_cr_sync_runs.id]
  test_case_id varchar(80) [not null]
  fixture_type varchar(80)
  user_id varchar(20)
  canonical_course_id varchar(50)
  expected_result varchar(100)
  actual_result varchar(100)
  passed boolean [not null]
  measured_value decimal(16, 4)
  detail text
  created_at bigint

  indexes {
    (sync_run_id)
    (test_case_id)
    (fixture_type)
    (passed)
  }
}
```

## 5. Table Notes

### 5.1 `local_cr_users`

Stores imported dataset users and their Moodle identity when seeded.

Important decision:

```text
user_id is the employee/dataset id.
moodle_userid is Moodle internal mdl_user.id.
```

Do not use employee ID as Moodle internal id.

### 5.2 `local_cr_courses`

Stores canonical course catalog from `courses.csv`.

`canonical_course_id` is stored as string to avoid type drift between CSV, API, PHP, and Python.

### 5.3 `local_cr_interactions`

Stores imported learning interactions.

`event_timestamp` is nullable because certified rows in the cleaned dataset do not have dates.

### 5.4 `local_cr_course_map`

Maps canonical course IDs to Moodle course IDs.

This is one of the most important integration tables.

### 5.5 `local_cr_sync_runs`

One row per sync attempt.

Used for:

```text
- idempotency
- audit trail
- evaluation metrics
- failure diagnosis
```

### 5.6 `local_cr_recommendations`

Stores recommendation cache.

Important fields:

```text
sync_run_id: identifies which sync produced the row
original_rank: rank from ML service
display_rank: optional rank after invalid candidates are filtered
is_active: dashboard reads only active rows
```

For MVP:

```text
preserve original_rank
display top-3 active rows sorted by original_rank
```

### 5.7 `local_cr_rec_skip`

Stores every skipped candidate and the reason it was skipped.

Required for evaluation.

Expected `skip_reason` values:

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

### 5.8 `local_cr_eval_results`

Stores deterministic fixture test results.

Used by CLI evaluation runner and optional admin diagnostic page.

## 6. Sync Atomicity Data Rule

Dashboard must only read:

```sql
WHERE is_active = 1
```

New sync rows are inserted with:

```text
is_active = 0
sync_run_id = current run id
```

Only after the complete paginated sync succeeds:

```text
1. deactivate previous active rows for affected users
2. activate rows from current sync_run_id
```

If sync fails:

```text
- keep old rows active
- leave new rows inactive or delete them
```

## 7. Privacy Notes

The local plugin stores user-related data and must not claim that it stores no personal data.

Minimum privacy provider should describe:

```text
- local_cr_users
- local_cr_interactions
- local_cr_recommendations
- local_cr_rec_skip, if user_id is stored
- local_cr_eval_results, if user_id is stored
```

The block plugin can use a null privacy provider only if it stores no user data directly.
