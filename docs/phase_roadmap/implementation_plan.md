# CRE Revised Implementation Plan

## 1. Purpose

This document defines the revised CRE implementation plan using three phases:

```text
Pre-MVP     -> ML service + simple PHP LMS simulator
MVP         -> Moodle plugin implementation for skripsi
Post-MVP    -> formal evaluation, paper/thesis package, and hardening
```

The main change from the earlier implementation plan is that Pre-MVP does not use Moodle. Instead, it uses a small PHP application that mimics the minimum LMS behavior needed to test the recommendation integration. Moodle is introduced in the MVP phase after the ML service, data flow, API security, and recommendation sync pattern have already been proven.

## 2. High-Level Strategy

The project should be built in increasing levels of realism.

### 2.1 Pre-MVP Strategy

Pre-MVP proves that the recommender system can work with the real dataset and can safely communicate with an LMS-like application.

It should answer:

```text
- Can the ML model generate useful recommendations from the real dataset?
- Can recommendations be exposed through a stable API contract?
- Can a PHP LMS-like client securely pull recommendations?
- Can canonical course IDs be mapped, cached, filtered, and displayed?
- Can API security be demonstrated clearly to a professor?
```

This phase should not claim to prove Moodle integration. It proves the integration pattern before Moodle.

### 2.2 MVP Strategy

MVP for skripsi proves the actual CRE integration claim inside Moodle.

It should answer:

```text
- Can the external ML recommendations be synchronized into Moodle?
- Can Moodle map canonical course IDs to Moodle course IDs?
- Can Moodle filter invalid, hidden, completed, or already enrolled courses?
- Can Moodle cache valid recommendations atomically?
- Can the dashboard display top-3 recommendations from cache?
- Can the dashboard remain safe when the ML service fails?
```

This is the main thesis prototype.

### 2.3 Post-MVP Strategy

Post-MVP turns the working prototype into academic evidence.

It should answer:

```text
- What are the measured results?
- How successful is mapping?
- How many recommendations are displayable?
- How fast is sync and dashboard rendering?
- Does failure handling work?
- Does the security design reject invalid requests?
- How should the work be written for thesis or paper publication?
```

Post-MVP may also include production hardening, but only after the academic evidence is complete.

## 3. Phase 1: Pre-MVP

## 3.1 Goal

Build a working ML recommendation service and a simple PHP LMS simulator using the real dataset and the proposed CRE schema concepts.

The Pre-MVP should be demoable without Moodle.

## 3.2 Scope

Included:

```text
- real cleaned dataset ingestion
- ML model training or batch recommendation generation
- recommendation export API
- optional per-user debug API
- simple PHP LMS simulator
- CRE-like schema in a normal database
- recommendation sync from ML service to PHP app
- API key or bearer token authentication
- HMAC request signing
- timestamp anti-replay validation
- request ID tracing
- sanitized logs
- simple dashboard showing top-3 recommendations
- ML quality evaluation
- API/security tests
```

Excluded:

```text
- Moodle installation
- Moodle plugin development
- Moodle block UI
- Moodle scheduled task API
- Moodle privacy provider
- Moodle capabilities
- production deployment hardening
```

## 3.3 Suggested Architecture

```text
Cleaned Dataset
users.csv, courses.csv, interactions.csv, course_alias_map.csv
        |
        v
ML Training / Batch Recommendation Job
        |
        v
ML Recommendation Service
GET /recommendations/export
GET /recommendations/user/{user_id}
        |
        v
Simple PHP LMS Simulator
- imports dataset tables
- stores LMS users/courses
- maps canonical_course_id to simulator course id
- pulls recommendations
- validates and caches recommendations
- displays top-3 recommendations
```

## 3.4 Pre-MVP Components

### 3.4.1 Dataset Preparation

Use the real cleaned dataset:

```text
users.csv
courses.csv
course_alias_map.csv
interactions.csv
```

Important rules:

```text
- user_id must remain string, preserving leading zeros
- canonical_course_id must remain string
- course names must not be used as the primary identifier
- interactions must keep enrolled/certified distinction
- training/evaluation split should be documented
```

### 3.4.2 ML Recommendation Service

The service should expose pre-generated recommendation candidates.

Required endpoint:

```http
GET /recommendations/export?model_version=latest&cursor={cursor}&limit=1000
```

Optional debug endpoint:

```http
GET /recommendations/user/{user_id}?model_version=latest
```

Required response fields:

```text
request_id
model_version
generated_at
page.limit
page.has_more
page.next_cursor
recommendations[].user_id
recommendations[].canonical_course_id
recommendations[].rank
recommendations[].score
recommendations[].reason_code
```

The ML service may load recommendations from:

```text
- model batch output CSV
- database table
- generated JSON file
- trained model inference output
```

For Pre-MVP, the most important thing is stable, reproducible output.

### 3.4.3 Pre-MVP Security

Implement the same security pattern that will later be reused by Moodle:

```text
- Authorization: Bearer {api_key}
- X-Request-Id
- X-Timestamp
- X-Signature
- HMAC-SHA256 signature
- timestamp expiry window
- constant-time signature comparison
- request timeout
- no secrets in logs
```

This lets the Pre-MVP demonstrate the future MVP security design early.

### 3.4.4 PHP LMS Simulator

The PHP app should mimic only the minimum LMS behavior needed for the integration.

Suggested features:

```text
- simple login or user selector
- user table
- course table
- course mapping table
- recommendation cache table
- sync run table
- skip reason table
- sync button or CLI command
- dashboard page showing top-3 recommendations
- admin/debug page showing last sync and metrics
```

The simulator should use schema names similar to the Moodle plugin schema, but it does not need to copy Moodle internals.

Suggested simulator tables:

```text
sim_users
sim_courses
sim_course_map
sim_sync_runs
sim_recommendations
sim_rec_skip
sim_security_logs
sim_model_eval_results
```

### 3.4.5 Pre-MVP Sync Flow

```text
1. PHP app creates sync_run_id.
2. PHP app calls ML export endpoint.
3. ML service validates API key, timestamp, and HMAC signature.
4. ML service returns one page of recommendation candidates.
5. PHP app validates payload shape.
6. PHP app maps canonical_course_id to local course id.
7. PHP app filters invalid rows.
8. PHP app stores valid rows as pending/inactive.
9. PHP app logs skipped rows.
10. PHP app continues until pagination is finished.
11. If all pages succeed, PHP app activates the new recommendation cache.
12. If any critical page fails, PHP app keeps previous active cache.
```

This mirrors the Moodle MVP sync flow.

### 3.4.6 Pre-MVP Evaluation

Pre-MVP should include two evaluation tracks.

ML quality evaluation:

```text
- Precision@3
- Precision@5 if useful
- Hit Rate@3
- NDCG@3
- sample user recommendation review
- comparison against baseline if available
```

Security/API evaluation:

```text
- valid request accepted
- missing API key rejected
- invalid API key rejected
- missing signature rejected
- invalid signature rejected
- expired timestamp rejected
- malformed response handled
- timeout handled
- secret not printed in logs
```

## 3.5 Pre-MVP Deliverables

```text
- running ML recommendation service
- generated recommendation output
- simple PHP LMS simulator
- database schema for simulator
- sync implementation
- dashboard page
- security implementation
- security test results
- ML quality result table
- short Pre-MVP demo script
```

## 3.6 Pre-MVP Exit Criteria

Pre-MVP is complete when:

```text
1. The ML service can produce recommendation candidates from the real dataset.
2. The export API returns paginated recommendations.
3. The PHP simulator can securely pull recommendations.
4. The simulator can map, validate, cache, and display top-3 recommendations.
5. Invalid or unmapped rows are skipped and logged.
6. API security tests can be demonstrated.
7. ML quality metrics can be shown.
8. The result is stable enough to port into Moodle.
```

## 4. Phase 2: MVP for Skripsi

## 4.1 Goal

Build the actual Moodle integration prototype using the ML service and integration pattern proven in Pre-MVP.

The MVP is the thesis system.

## 4.2 Scope

Included:

```text
- Moodle local plugin
- Moodle block plugin
- Moodle plugin database tables
- dataset import into Moodle plugin tables
- Moodle demo user/course seeding
- canonical_course_id to Moodle course mapping
- secure ML export API client
- atomic recommendation sync
- skip reason logging
- scheduled task and CLI sync
- dashboard block
- admin diagnostics
- stale/empty states
- basic Moodle privacy provider
- evaluation instrumentation
```

Excluded:

```text
- public production deployment
- complex analytics dashboard
- manager dashboard
- queue-based production sync
- A/B testing
- LLM-generated explanations
- mTLS or private VPC setup
```

## 4.3 Moodle Architecture

```text
ML Recommendation Service
        |
        | signed paginated API pull
        v
local_courserecommender
- data import
- course mapping
- sync client
- validation
- recommendation cache
- logs
- diagnostics
        |
        | database read
        v
block_courserecommender
- dashboard top-3 UI
- empty state
- stale state
- course links
```

The dashboard block must never call the ML service directly.

## 4.4 Moodle Plugin Responsibilities

### 4.4.1 `local_courserecommender`

Responsibilities:

```text
- create plugin tables
- import cleaned dataset
- seed Moodle demo data
- map canonical_course_id to Moodle course id
- call ML export API
- validate payloads
- validate Moodle display eligibility
- cache valid recommendations
- log skipped recommendations
- log sync metrics
- provide scheduled task
- provide CLI commands
- provide diagnostics page
- implement basic privacy provider
```

### 4.4.2 `block_courserecommender`

Responsibilities:

```text
- identify current Moodle user
- find matching local_cr_users row
- read active cached recommendations
- sort by original_rank
- display top-3 recommendations
- show score plainly
- link to Moodle course page
- show empty state
- show stale state
- implement null privacy provider if no data is stored directly
```

Non-responsibilities:

```text
- calling ML service
- running sync
- importing data
- performing heavy validation
```

## 4.5 MVP Database Tables

Use the schema from the existing database design:

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

Key table behavior:

```text
- local_cr_recommendations.is_active controls dashboard visibility
- new sync rows start inactive
- rows activate only after complete sync success
- failed sync must not wipe old active rows
- skip reasons must be stored for evaluation
```

## 4.6 MVP Sync Flow

```text
1. Moodle scheduled task, CLI command, or admin action starts sync.
2. local_courserecommender creates local_cr_sync_runs row.
3. ML client signs request.
4. ML client calls export endpoint.
5. ML client loops through all pages.
6. sync_service validates every row.
7. sync_service checks user existence.
8. sync_service maps canonical_course_id to Moodle course id.
9. sync_service checks Moodle course exists.
10. sync_service checks course visibility.
11. sync_service checks user completion status.
12. sync_service checks current enrolment status.
13. sync_service rejects duplicate recommendations.
14. sync_service inserts valid recommendations as inactive.
15. sync_service logs skipped rows with skip_reason.
16. If all pages succeed, old rows for affected users are deactivated.
17. New rows from the sync_run_id are activated.
18. local_cr_sync_runs is marked success.
19. If a critical error occurs, local_cr_sync_runs is marked failed.
20. Existing active cache remains untouched after failure.
```

## 4.7 MVP Validation Rules

Rows should be skipped if:

```text
- user_id is missing
- canonical_course_id is missing
- rank is missing or non-positive
- score is missing or invalid
- user does not exist in local_cr_users
- user is not mapped to a Moodle user
- canonical_course_id is not mapped
- mapped Moodle course does not exist
- Moodle course is hidden
- user already completed the course
- user is already enrolled
- duplicate user_id + canonical_course_id appears in same sync run
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

## 4.8 MVP Security

Reuse the Pre-MVP security model:

```text
- API key or bearer token
- HMAC-SHA256 signature
- timestamp anti-replay
- request ID
- HTTP timeout
- sanitized logs
- no hardcoded secrets
- secrets stored in Moodle config or environment variables
```

Moodle should test:

```text
- valid request accepted
- missing API key rejected
- invalid API key rejected
- invalid HMAC rejected
- expired timestamp rejected
- timeout handled
- service unavailable handled
```

## 4.9 MVP Dashboard Behavior

Dashboard block should:

```text
- load current Moodle user
- find local_cr_users by moodle_userid
- query local_cr_recommendations where is_active = 1
- order by original_rank
- display top-3
- show course name
- show score as match percentage
- link to course view page
- show empty state if no recommendations
- show stale state if generated_at is older than configured threshold
```

Dashboard block should not:

```text
- call ML API
- trigger sync automatically
- display invalid courses
- display hidden courses
- display completed courses
- fake explanation text if reason_code is empty
```

## 4.10 MVP Evaluation Instrumentation

The MVP must store enough data to support Post-MVP evaluation.

Instrumentation should capture:

```text
- sync start time
- sync finish time
- sync duration
- API latency
- model_version
- total pages
- total rows received
- total mapped
- total displayable
- total skipped
- skip reason counts
- active recommendation count
- dashboard render time if feasible
```

Important: do not postpone instrumentation until Post-MVP. The paper/evaluation phase depends on data generated during MVP.

## 4.11 MVP Deliverables

```text
- local_courserecommender plugin
- block_courserecommender plugin
- Moodle installable database schema
- dataset import CLI
- Moodle demo seed CLI
- secure ML client
- sync service
- scheduled task
- CLI sync command
- admin diagnostics page
- dashboard recommendation block
- privacy provider
- fixture/evaluation runner foundation
```

## 4.12 MVP Exit Criteria

MVP is complete when:

```text
1. Plugins install without modifying Moodle core.
2. Cleaned dataset can be imported into Moodle plugin tables.
3. Moodle demo users and courses can be seeded.
4. canonical_course_id can be mapped to Moodle course id.
5. Moodle can securely pull ML recommendation export.
6. Sync is atomic and idempotent.
7. Invalid candidates are skipped and logged.
8. Dashboard displays top-3 cached recommendations.
9. Stale and empty states work.
10. ML failure does not break the dashboard.
11. Sync metrics are stored for evaluation.
12. Basic security tests pass.
```

## 5. Phase 3: Post-MVP

## 5.1 Goal

Turn the working Moodle MVP into formal thesis/paper evidence and optionally harden the system.

Post-MVP is not where core functionality should first be built. It is where results are finalized, analyzed, documented, and prepared for publication.

## 5.2 Scope

Included:

```text
- formal functional evaluation
- mapping evaluation
- displayability evaluation
- performance evaluation
- failure handling evaluation
- security evaluation
- privacy/logging evaluation
- screenshots and evidence collection
- thesis/paper writing
- limitations and future work
- optional hardening
```

Optional:

```text
- Docker setup
- CI tests
- nicer admin UI
- richer diagnostics
- monitoring
- production deployment documentation
```

## 5.3 Formal Evaluation Plan

### 5.3.1 Functional Evaluation

Measure whether required system behaviors pass.

Examples:

```text
- dataset import succeeds
- Moodle course mapping succeeds
- ML sync succeeds
- hidden course is skipped
- completed course is skipped
- already enrolled course is skipped
- duplicate recommendation is skipped
- dashboard displays top-3
- empty state appears
- stale state appears
- ML failure leaves old cache active
```

Metric:

```text
Functional Pass Rate = passed test cases / total test cases
```

### 5.3.2 Mapping Evaluation

Metric:

```text
Mapping Success Rate = mapped recommendation rows / total recommendation rows received
```

Report:

```text
- total received
- mapped count
- unmapped count
- mapping success rate
```

### 5.3.3 Displayability Evaluation

Metric:

```text
Displayable Recommendation Rate = displayable rows / total recommendation rows received
```

Report:

```text
- total displayable
- total skipped
- skip reason counts
```

### 5.3.4 Performance Evaluation

Measure:

```text
- ML export API latency
- Moodle sync duration
- validation/mapping duration if available
- dashboard render time from cache
```

Run each measurement multiple times and report:

```text
- average
- minimum
- maximum
- target comparison
```

### 5.3.5 Failure Handling Evaluation

Test:

```text
- ML service unavailable
- endpoint timeout
- HTTP 500
- malformed JSON
- missing required fields
- invalid score
- invalid rank
```

Expected:

```text
- sync marked failed
- error logged
- pending rows not activated
- previous active cache remains available
- dashboard still loads
```

### 5.3.6 Security Evaluation

Test:

```text
- valid request accepted
- missing API key rejected
- invalid API key rejected
- missing signature rejected
- invalid signature rejected
- expired timestamp rejected
- raw secret absent from logs
- hardcoded secret absent from source
```

### 5.3.7 ML Quality Evaluation

Use the Pre-MVP ML metrics as supporting evidence.

Possible metrics:

```text
- Precision@3
- Hit Rate@3
- NDCG@3
- expert relevance rate
```

Positioning:

```text
The primary contribution is Moodle integration.
The ML quality result is supporting evidence.
```

## 5.4 Evidence Package

Post-MVP should produce:

```text
- architecture diagram
- database schema diagram
- API contract summary
- security design summary
- functional test table
- mapping success table
- displayability table
- skip reason count table
- performance table
- failure handling table
- security test table
- privacy/logging checklist
- dashboard screenshots
- admin diagnostics screenshots
- sanitized sync logs
- exported evaluation CSV
```

## 5.5 Thesis/Paper Structure

Suggested structure:

```text
1. Introduction
2. Problem statement
3. Related work
4. Dataset description
5. System architecture
6. ML recommendation service overview
7. Moodle integration design
8. Security design
9. Implementation
10. Evaluation method
11. Evaluation results
12. Discussion
13. Limitations
14. Conclusion
15. Future work
```

## 5.6 Post-MVP Exit Criteria

Post-MVP is complete when:

```text
1. All evaluation tables are produced.
2. Screenshots and logs are collected.
3. Results are analyzed.
4. Thesis/paper sections are drafted.
5. Limitations are clearly stated.
6. Future work is separated from MVP claims.
7. The system can be demonstrated end-to-end.
```

## 6. Recommended Phase Boundaries

## 6.1 What Must Be Done Before Moving From Pre-MVP to MVP

Do not start Moodle implementation until:

```text
- ML export API response shape is stable
- HMAC/API key security works
- recommendation output is reproducible
- PHP simulator can sync and display recommendations
- ML quality metrics are available
- security demo can be shown
```

## 6.2 What Must Be Done Before Moving From MVP to Post-MVP

Do not start formal paper evaluation until:

```text
- Moodle sync works
- dashboard block works
- skip logging works
- diagnostics metrics are stored
- failure handling works
- at least one fixture sync has passed
```

## 6.3 What Should Stay Out of Skripsi MVP

Keep these out unless explicitly required:

```text
- manager dashboard
- real production deployment
- queue system
- A/B testing
- LLM explanations
- public internet deployment
- mobile customization
- complex role-based recommendation policy
- advanced skill taxonomy
```

## 7. Main Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Pre-MVP is mistaken as final system | Weak thesis integration claim | Present Pre-MVP as simulator only |
| ML model quality becomes main expectation | Scope expands beyond integration | Label ML quality as supporting evidence |
| Moodle complexity delays progress | MVP blocked | Prove API and sync in PHP first |
| Security implementation differs between phases | Duplicate work | Reuse same HMAC/API contract |
| Evaluation data is not captured during MVP | Post-MVP becomes manual | Add instrumentation during MVP |
| Course IDs drift between services | Mapping fails | Store IDs as strings everywhere |
| user_id leading zeros are lost | User mapping fails | Treat user_id as string everywhere |
| Failed sync wipes cache | Dashboard loses recommendations | Use inactive staging and atomic activation |

## 8. Recommended Narrative for Professor

The recommended explanation is:

```text
The project is implemented in three phases. First, a Pre-MVP simulator validates the ML recommendation service, the API contract, the real dataset pipeline, and the security mechanism without Moodle complexity. Second, the MVP ports the validated design into Moodle using a local plugin and dashboard block. Third, Post-MVP performs formal evaluation and prepares the academic paper or thesis evidence.
```

This narrative is clear because each phase has a different purpose:

```text
Pre-MVP proves feasibility.
MVP proves Moodle integration.
Post-MVP proves academic validity.
```

