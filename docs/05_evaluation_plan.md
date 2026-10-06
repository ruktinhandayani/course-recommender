# CRE Evaluation Plan

## 1. Evaluation Goal

The evaluation must prove that CRE works as a Moodle and ML integration system.

The minimum claim:

```text
The system synchronizes external ML recommendation candidates into Moodle, maps canonical course identifiers, filters non-displayable recommendations, caches valid results, renders recommendations from cache, and fails safely when the ML service is unavailable.
```

## 2. Evaluation Scope

Evaluate:

```text
- functional correctness
- mapping success
- displayability validation
- performance
- failure handling
- basic security
- privacy/logging behavior
```

Do not make ML model quality the primary evaluation because the project focus is integration.

Recommendation quality metrics may be reported as supporting evidence if available.

## 3. Data Setup

Use two data layers.

### 3.1 Cleaned Research Dataset

Import full cleaned data into plugin tables:

```text
users.csv: 9,598 users
courses.csv: 1,114 canonical courses
interactions.csv: 77,600 interactions
course_alias_map.csv: 1,148 aliases
```

Purpose:

```text
- realistic data scale
- mapping and interaction context
- thesis dataset description
```

### 3.2 Moodle Evaluation Subset

Recommended minimum:

```text
300 Moodle users
1,114 Moodle courses if feasible
top-20 recommendation candidates per user
around 6,000 recommendation candidate rows
```

If all 1,114 Moodle courses cannot be created, use at least 500 courses selected from recommendation candidates and high-interaction courses.

## 4. User Selection Logic

Select approximately 300 users using stratified sampling:

```text
100 active users:
- users with more than 10 interactions

100 medium users:
- users with 3 to 10 interactions

50 sparse users:
- users with 1 to 2 interactions

30 certified users:
- users with at least one certified interaction

20 edge-case users:
- users used for no-recommendation, stale-cache, or failure scenarios
```

Implementation logic:

```text
1. Group interactions.csv by user_id.
2. Count interactions per user.
3. Mark users with certified interactions.
4. Select users from each group.
5. Create Moodle users with username/idnumber = user_id.
6. Store moodle_userid in local_cr_users.
```

## 5. Course Selection Logic

Preferred:

```text
Create Moodle courses for all 1,114 canonical courses.
```

If using subset:

```text
1. Select courses appearing in recommendation output.
2. Include high-interaction courses.
3. Include some courses with missing description/level/kompetensi.
4. Reserve several real canonical_course_id values as intentionally unmapped.
```

## 6. Recommendation Candidate Setup

Use:

```text
top_k = 20
```

Reason:

```text
Moodle filters invalid candidates. Top-20 gives enough candidates to still display top-3 valid courses.
```

Expected scale:

```text
300 users x top-20 = 6,000 candidate rows
```

## 7. Controlled Test Fixtures

Create deterministic test fixture rows for edge cases.

Suggested file:

```text
recommendation_test_fixtures.csv
```

Columns:

```text
test_case_id
user_id
canonical_course_id
rank
score
reason_code
expected_result
fixture_type
```

Example:

```csv
test_case_id,user_id,canonical_course_id,rank,score,reason_code,expected_result,fixture_type
TC_VALID_001,000123451,183,1,0.9231,,display,valid
TC_UNMAPPED_001,000123451,52,2,0.8814,,skip_unmapped,unmapped
TC_HIDDEN_001,000123452,60,1,0.9022,,skip_hidden,hidden
TC_COMPLETED_001,000123453,183,1,0.8999,,skip_completed,completed
```

Fixture sync should use:

```text
run_type = fixture
```

Do not mix fixture results with normal sync results.

## 8. Minimum Test Case Counts

| Test Group | Minimum Count | Purpose |
|---|---:|---|
| Valid recommendation | 100+ users | Prove normal display |
| Unmapped course | 20 rows | Prove mapping filter |
| Hidden course | 20 rows | Prove visibility filter |
| Completed course | 50 rows | Prove completion filter |
| Already enrolled course | 50 rows | Prove new-course-only rule |
| User with no recommendations | 10 users | Prove empty state |
| Stale cache | 10 users | Prove stale handling |
| ML service failure | 3 scenarios | Prove safe failure |
| Invalid API response | 3 scenarios | Prove parser/error handling |
| Duplicate recommendation | 10 rows | Prove deduplication |

## 9. Functional Evaluation

Functional test flow:

```text
1. Seed dataset.
2. Seed Moodle demo state.
3. Run normal recommendation sync.
4. Run fixture sync.
5. Open dashboard as selected users.
6. Verify displayed recommendations.
7. Export sync/evaluation logs.
```

Functional pass rate:

```text
Functional Pass Rate = passed test cases / total test cases
```

Required evidence:

```text
- pass/fail table
- screenshots of dashboard recommendation block
- screenshot or export of admin diagnostics
- sync logs
- evaluation CSV
```

## 10. Mapping Evaluation

Metric:

```text
Mapping Success Rate =
mapped recommendation rows / total recommendation rows received
```

Report:

```text
- total received
- mapped count
- unmapped count
- mapping success rate
```

## 11. Displayability Evaluation

Metric:

```text
Displayable Recommendation Rate =
displayable recommendation rows / total recommendation rows received
```

Report skip reason counts:

```text
user_not_found
course_not_found
unmapped_course
hidden_course
completed_course
already_enrolled
duplicate_recommendation
invalid_payload
invalid_rank
invalid_score
```

Required evidence:

```text
- local_cr_rec_skip export
- local_cr_sync_runs summary
- fixture expected vs actual results
```

## 12. Performance Evaluation

Measure at least:

```text
- ML export API latency
- Moodle sync duration
- validation/mapping duration if available
- dashboard block render time from cache
```

Run each measurement at least 10 times.

Report:

```text
- average
- minimum
- maximum
```

Target:

```text
dashboard block render time from cache < 500 ms
ML API timeout around 5 seconds
```

Example table:

| Metric | Average | Maximum | Target |
|---|---:|---:|---:|
| ML export API latency | 320 ms | 610 ms | < 5 s |
| Moodle sync duration, 6,000 rows | 4.8 s | 5.5 s | < 30 s |
| Dashboard block render time | 74 ms | 130 ms | < 500 ms |

## 13. Failure Handling Evaluation

Scenarios:

```text
1. ML service unavailable
2. ML endpoint timeout
3. ML service returns HTTP 500
4. ML service returns malformed JSON
5. ML service returns rows missing required fields
```

Expected result:

```text
- sync run marked failed
- error logged
- pending rows not activated
- old active cache remains available
- dashboard still loads
```

Required evidence:

```text
- failed sync log
- dashboard screenshot after failure
- active recommendation count before/after failure
```

## 14. Security Evaluation

Minimum tests:

| Security Test | Expected Result |
|---|---|
| Missing API key | Request rejected |
| Invalid API key | Request rejected |
| Missing signature | Request rejected |
| Invalid signature | Request rejected |
| Expired timestamp | Request rejected |
| Raw employee ID in operational logs | Not present or masked |
| Secret hardcoded in source | Not present |

Required evidence:

```text
- test result table
- sample sanitized logs
- configuration explanation
```

## 15. Privacy Evaluation

Minimum checks:

```text
- local plugin declares stored user-related data through privacy provider
- block plugin declares no stored user data if applicable
- raw employee_id is not written to operational error logs
- API secrets are not exported in logs
```

If implemented:

```text
- test export of one user's recommendation data
- test deletion/anonymization of one user's recommendation data
```

## 16. Example Result Tables

### 16.1 Functional Result

| Test Group | Cases | Expected Behavior | Result |
|---|---:|---|---|
| Valid recommendation | 300 users | Display top-3 cached courses | Pass |
| Unmapped course | 20 rows | Skipped and logged as unmapped_course | Pass |
| Hidden course | 20 rows | Skipped and logged as hidden_course | Pass |
| Completed course | 50 rows | Skipped and logged as completed_course | Pass |
| Already enrolled | 50 rows | Skipped and logged as already_enrolled | Pass |
| No recommendation | 10 users | Empty state shown | Pass |
| Stale cache | 10 users | Stale state handled | Pass |
| ML failure | 3 scenarios | Sync fails safely, dashboard works | Pass |
| Invalid response | 3 scenarios | Response rejected and logged | Pass |
| Duplicate row | 10 rows | Duplicate removed or rejected | Pass |

### 16.2 Mapping and Displayability Result

| Metric | Value |
|---|---:|
| Recommendations received | 6,000 |
| Mapped recommendations | 5,820 |
| Displayable recommendations | 5,410 |
| Skipped unmapped | 180 |
| Skipped hidden | 20 |
| Skipped completed | 350 |
| Skipped already enrolled | 50 |
| Skipped duplicate | 40 |
| Mapping success rate | 97.00% |
| Displayable recommendation rate | 90.17% |

## 17. Minimum SINTA 3 Proof Package

The minimum defensible evidence package:

```text
1. architecture diagram
2. database schema
3. API contract
4. functional test table
5. mapping success rate
6. displayable recommendation rate
7. skip reason counts
8. performance table
9. failure handling table
10. security test table
11. screenshots of dashboard/admin diagnostics
12. sanitized sync logs
```

## 18. Optional Supporting Recommendation Quality

If available, report:

```text
- Precision@3
- Hit Rate@3
- NDCG@3
- expert relevance rate
```

These are supporting metrics only. The main evaluation remains integration correctness and system behavior.
