# CRE AI Agent Implementation Todo

## 1. Instructions for the AI Agent

You are implementing CRE in three phases:

```text
Phase 1: Pre-MVP
ML recommendation service + simple PHP LMS simulator.

Phase 2: MVP for Skripsi
Real Moodle implementation using local and block plugins.

Phase 3: Post-MVP
Formal evaluation, evidence package, thesis/paper preparation, and optional hardening.
```

Before implementing anything, read the project source-of-truth documents in this order:

```text
1. ../01_final_architecture_design.md
2. ../02_database_schema.md
3. ../03_api_contract.md
4. ../04_implementation_task_list.md
5. ../05_evaluation_plan.md
```

Then read:

```text
6. implementation_plan.md
7. detailed_todo.md
```

The five numbered documents are the source of truth for architecture, schema, API, implementation requirements, and evaluation requirements.

The files in `phase_roadmap/` are the source of truth for the revised phase split:

```text
Pre-MVP uses a PHP LMS simulator, not Moodle.
MVP uses Moodle.
Post-MVP performs formal evaluation and writing.
```

If there is a conflict:

```text
1. Use the five numbered documents for technical rules.
2. Use phase_roadmap/implementation_plan.md for phase boundaries.
3. Use this file for agent execution order.
```

## 2. Global Implementation Rules

Follow these rules in every phase:

- [ ] Do not use course names as identifiers.
- [ ] Treat `user_id` as a string everywhere.
- [ ] Preserve leading zeros in `user_id`.
- [ ] Treat `canonical_course_id` as a string everywhere.
- [ ] Do not expose Moodle internal `course.id` to the ML service.
- [ ] Do not hardcode secrets.
- [ ] Do not log API keys, HMAC secrets, or raw sensitive payloads.
- [ ] Use request IDs for traceability.
- [ ] Use atomic sync behavior: failed sync must not wipe active cache.
- [ ] Store skipped recommendations with explicit skip reasons.
- [ ] Keep dashboard rendering cache-based.
- [ ] Do not make dashboard pages call the ML service directly.
- [ ] Keep ML quality as supporting evidence, not the main system contribution.
- [ ] Keep the main contribution focused on secure LMS integration.

## 3. Phase 1: Pre-MVP Agent Todo

## 3.1 Phase Goal

Implement a working ML recommendation service and simple PHP LMS simulator using the real dataset.

The Pre-MVP must prove:

```text
- ML recommendations can be generated from the real dataset.
- Recommendations can be exposed through the planned API contract.
- A PHP LMS-like client can securely pull recommendations.
- Recommendations can be mapped, filtered, cached, and displayed.
- API security can be demonstrated.
```

Do not use Moodle in this phase.

## 3.2 Required Source Documents

Before coding Phase 1, read:

- [ ] `../03_api_contract.md`
- [ ] `../02_database_schema.md`
- [ ] `../05_evaluation_plan.md`
- [ ] `implementation_plan.md`, especially Phase 1
- [ ] `detailed_todo.md`, especially Pre-MVP Todo

Use `../03_api_contract.md` as the primary source for the ML API.

Use `../02_database_schema.md` as the inspiration for simulator schema, but adapt table names to simulator names.

## 3.3 Deliverables

Produce:

- [ ] ML recommendation service.
- [ ] Recommendation generation or recommendation output loader.
- [ ] `GET /recommendations/export` endpoint.
- [ ] Optional `GET /recommendations/user/{user_id}` endpoint.
- [ ] API key or bearer token authentication.
- [ ] HMAC-SHA256 request signing validation.
- [ ] Timestamp anti-replay validation.
- [ ] Simple PHP LMS simulator.
- [ ] Simulator database schema.
- [ ] Dataset import script.
- [ ] Recommendation sync script or admin action.
- [ ] Recommendation cache.
- [ ] Skip reason logging.
- [ ] Simple dashboard showing top-3 recommendations.
- [ ] Admin/debug page showing sync metrics.
- [ ] ML quality evaluation output.
- [ ] Security test output.

## 3.4 Recommended Implementation Order

### Step 1: Create Pre-MVP Project Structure

- [ ] Create a clear directory for Pre-MVP code.
- [ ] Create subdirectory for ML service.
- [ ] Create subdirectory for PHP simulator.
- [ ] Create subdirectory for dataset import scripts.
- [ ] Create subdirectory for generated/evaluation outputs.
- [ ] Add README explaining how to run Pre-MVP.
- [ ] Add environment/config example file.
- [ ] Add local ignored config file for secrets.

Completion evidence:

- [ ] Directory structure exists.
- [ ] README has run instructions.
- [ ] Secrets are not committed into source files.

### Step 2: Validate Real Dataset

- [ ] Load `users.csv`.
- [ ] Load `courses.csv`.
- [ ] Load `course_alias_map.csv`.
- [ ] Load `interactions.csv`.
- [ ] Validate required columns.
- [ ] Count rows in each file.
- [ ] Check duplicate `user_id` values.
- [ ] Check duplicate `canonical_course_id` values.
- [ ] Check missing `canonical_course_id` values.
- [ ] Check that `user_id` leading zeros are preserved.
- [ ] Save validation summary.

Completion evidence:

- [ ] Dataset validation summary file exists.
- [ ] Validation script can be rerun.
- [ ] Any dataset assumptions are documented.

### Step 3: Generate ML Recommendations

- [ ] Implement or call the chosen recommendation algorithm.
- [ ] Generate top-20 recommendation candidates per selected user.
- [ ] Store output with `user_id`.
- [ ] Store output with `canonical_course_id`.
- [ ] Store output with `rank`.
- [ ] Store output with `score`.
- [ ] Store output with `model_version`.
- [ ] Store output with `generated_at`.
- [ ] Ensure output is deterministic for repeated test runs.
- [ ] Ensure output does not contain Moodle internal IDs.

Completion evidence:

- [ ] Recommendation output file or table exists.
- [ ] Sample output follows API contract.
- [ ] Model version is visible.

### Step 4: Implement ML Export API

- [ ] Implement `GET /recommendations/export`.
- [ ] Support `model_version=latest`.
- [ ] Support exact `model_version` if feasible.
- [ ] Support `cursor`.
- [ ] Support `limit`.
- [ ] Enforce maximum limit of 1000.
- [ ] Return `request_id`.
- [ ] Return `model_version`.
- [ ] Return `generated_at`.
- [ ] Return `page.limit`.
- [ ] Return `page.has_more`.
- [ ] Return `page.next_cursor`.
- [ ] Return `recommendations`.
- [ ] Return structured error responses.
- [ ] Add optional fixture/test mode if useful.

Completion evidence:

- [ ] Example successful API response.
- [ ] Example paginated response.
- [ ] Example error response.

### Step 5: Implement API Security

- [ ] Require `Authorization: Bearer {api_key}`.
- [ ] Require `X-Request-Id`.
- [ ] Require `X-Timestamp`.
- [ ] Require `X-Signature`.
- [ ] Implement canonical signing string from `../03_api_contract.md`.
- [ ] Validate HMAC-SHA256.
- [ ] Validate timestamp expiry.
- [ ] Use constant-time comparison for signatures.
- [ ] Reject missing API key.
- [ ] Reject invalid API key.
- [ ] Reject missing signature.
- [ ] Reject invalid signature.
- [ ] Reject expired timestamp.
- [ ] Mask secrets in logs.

Completion evidence:

- [ ] Security tests show valid request accepted.
- [ ] Security tests show invalid requests rejected.
- [ ] Logs do not expose secrets.

### Step 6: Implement PHP Simulator Schema

- [ ] Create simulator database migration or SQL file.
- [ ] Create `sim_users`.
- [ ] Create `sim_courses`.
- [ ] Create `sim_course_map`.
- [ ] Create `sim_sync_runs`.
- [ ] Create `sim_recommendations`.
- [ ] Create `sim_rec_skip`.
- [ ] Add indexes for user lookup.
- [ ] Add indexes for course mapping lookup.
- [ ] Add indexes for active recommendation lookup.
- [ ] Add indexes for skip reason analysis.

Completion evidence:

- [ ] Database can be created from scratch.
- [ ] Schema file or migration exists.
- [ ] Indexes are included.

### Step 7: Implement PHP Simulator Data Import

- [ ] Import users.
- [ ] Import courses.
- [ ] Create simulator course records.
- [ ] Create canonical course mappings.
- [ ] Create hidden course fixtures.
- [ ] Create completed course fixtures.
- [ ] Create already enrolled course fixtures.
- [ ] Reserve unmapped course fixtures.
- [ ] Make import idempotent.
- [ ] Print import summary.

Completion evidence:

- [ ] Import can run twice without corrupting data.
- [ ] Import summary shows counts.
- [ ] Fixture cases exist.

### Step 8: Implement PHP Simulator Sync

- [ ] Build signed API client.
- [ ] Create sync run.
- [ ] Pull first export page.
- [ ] Pull all export pages.
- [ ] Validate payload shape.
- [ ] Validate user IDs.
- [ ] Validate course IDs.
- [ ] Validate rank.
- [ ] Validate score.
- [ ] Detect duplicates.
- [ ] Map course IDs.
- [ ] Filter hidden courses.
- [ ] Filter completed courses.
- [ ] Filter already enrolled courses.
- [ ] Insert valid recommendations as inactive.
- [ ] Insert skip logs.
- [ ] Activate new recommendations after full success.
- [ ] Preserve old active cache after failure.
- [ ] Store sync metrics.

Completion evidence:

- [ ] Successful sync summary.
- [ ] Failed sync does not remove previous active recommendations.
- [ ] Skip reason logs exist.

### Step 9: Implement PHP Simulator UI

- [ ] Build user selector or simple login.
- [ ] Build dashboard page.
- [ ] Query active recommendations.
- [ ] Show top-3 recommendations.
- [ ] Show score as match percentage.
- [ ] Show course name.
- [ ] Show course link.
- [ ] Show empty state.
- [ ] Show stale state.
- [ ] Build admin/debug page.
- [ ] Show last sync status.
- [ ] Show received/mapped/displayable/skipped counts.
- [ ] Show skip reason counts.

Completion evidence:

- [ ] Dashboard screenshot.
- [ ] Admin/debug screenshot.
- [ ] Empty and stale states can be demonstrated.

### Step 10: Run Pre-MVP Evaluation

- [ ] Run ML quality evaluation.
- [ ] Calculate Precision@3.
- [ ] Calculate Hit Rate@3.
- [ ] Calculate NDCG@3.
- [ ] Run security tests.
- [ ] Run sync failure test.
- [ ] Run malformed response test.
- [ ] Export result tables.
- [ ] Write short Pre-MVP result summary.

Completion evidence:

- [ ] ML quality table exists.
- [ ] Security test table exists.
- [ ] Pre-MVP demo script exists.

## 3.5 Phase 1 Done Criteria

Phase 1 is done only when:

- [ ] ML service runs.
- [ ] PHP simulator runs.
- [ ] Real dataset is imported.
- [ ] Recommendations are generated.
- [ ] Export API works.
- [ ] API security works.
- [ ] Simulator sync works.
- [ ] Recommendations are cached atomically.
- [ ] Dashboard displays top-3.
- [ ] Invalid recommendations are skipped and logged.
- [ ] ML quality metrics are available.
- [ ] Security tests are available.

## 4. Phase 2: MVP for Skripsi Agent Todo

## 4.1 Phase Goal

Implement the real Moodle version of CRE using the ML service and security pattern proven in Pre-MVP.

The MVP must prove:

```text
External ML recommendations can be securely synchronized into Moodle, mapped to Moodle courses, filtered according to Moodle state, cached atomically, and displayed from cache on the Moodle dashboard.
```

## 4.2 Required Source Documents

Before coding Phase 2, read:

- [ ] `../01_final_architecture_design.md`
- [ ] `../02_database_schema.md`
- [ ] `../03_api_contract.md`
- [ ] `../04_implementation_task_list.md`
- [ ] `../05_evaluation_plan.md`
- [ ] `implementation_plan.md`, especially Phase 2
- [ ] `detailed_todo.md`, especially MVP for Skripsi Todo

Use the five numbered documents as the technical source of truth.

## 4.3 Deliverables

Produce:

- [ ] `local_courserecommender` Moodle plugin.
- [ ] `block_courserecommender` Moodle plugin.
- [ ] Moodle plugin database tables.
- [ ] Dataset import CLI.
- [ ] Moodle demo seed CLI.
- [ ] Setup wrapper CLI.
- [ ] Secure ML API client.
- [ ] Atomic sync service.
- [ ] Skip reason logging.
- [ ] Scheduled task.
- [ ] CLI sync command.
- [ ] Admin diagnostics page.
- [ ] Dashboard recommendation block.
- [ ] Basic privacy provider.
- [ ] Evaluation runner foundation.

## 4.4 Recommended Implementation Order

### Step 1: Prepare Moodle Environment

- [ ] Confirm Moodle 5.x local environment runs.
- [ ] Confirm database access.
- [ ] Confirm cron can run.
- [ ] Confirm admin login works.
- [ ] Confirm plugin installation workflow.
- [ ] Enable development debugging.

Completion evidence:

- [ ] Moodle site loads.
- [ ] Admin can install plugins.
- [ ] Cron can be executed.

### Step 2: Create Moodle Plugin Skeletons

- [ ] Create `local_courserecommender`.
- [ ] Add `version.php`.
- [ ] Add `settings.php`.
- [ ] Add language strings.
- [ ] Add `db/install.xml`.
- [ ] Add `db/access.php`.
- [ ] Add `db/tasks.php`.
- [ ] Add service class directories.
- [ ] Add CLI directory.
- [ ] Add diagnostics page placeholder.
- [ ] Create `block_courserecommender`.
- [ ] Add block `version.php`.
- [ ] Add block language strings.
- [ ] Add block class.
- [ ] Add block empty state.
- [ ] Install both plugins.

Completion evidence:

- [ ] Plugins install successfully.
- [ ] Block can be added to dashboard.
- [ ] Empty state renders.

### Step 3: Implement Moodle Database Schema

- [ ] Implement `local_cr_users`.
- [ ] Implement `local_cr_courses`.
- [ ] Implement `local_cr_course_alias`.
- [ ] Implement `local_cr_interactions`.
- [ ] Implement `local_cr_course_map`.
- [ ] Implement `local_cr_sync_runs`.
- [ ] Implement `local_cr_recommendations`.
- [ ] Implement `local_cr_rec_skip`.
- [ ] Implement `local_cr_eval_results`.
- [ ] Add required indexes from `../02_database_schema.md`.
- [ ] Add uniqueness rules.
- [ ] Test clean install.
- [ ] Test upgrade path if plugin already installed.

Completion evidence:

- [ ] Tables exist in Moodle database.
- [ ] Indexes exist.
- [ ] Plugin install has no XMLDB errors.

### Step 4: Implement Moodle Settings and Capabilities

- [ ] Add ML service base URL setting.
- [ ] Add API key setting.
- [ ] Add HMAC secret setting or environment reference.
- [ ] Add timeout setting.
- [ ] Add stale threshold setting.
- [ ] Add page limit setting.
- [ ] Define `local/courserecommender:viewdiagnostics`.
- [ ] Define `local/courserecommender:runsync`.
- [ ] Define `local/courserecommender:exportlogs`.
- [ ] Restrict admin features to site admins.

Completion evidence:

- [ ] Settings page works.
- [ ] Capabilities are registered.
- [ ] Unauthorized users cannot access diagnostics.

### Step 5: Implement Dataset Import CLI

- [ ] Create `cli/seed_dataset.php`.
- [ ] Support `--data-dir`.
- [ ] Import users.
- [ ] Import courses.
- [ ] Import aliases.
- [ ] Import interactions.
- [ ] Preserve leading zeros.
- [ ] Store IDs as strings.
- [ ] Make import idempotent.
- [ ] Validate required columns.
- [ ] Print import summary.

Completion evidence:

- [ ] CLI import runs.
- [ ] Row counts match expectations.
- [ ] Re-running import is safe.

### Step 6: Implement Moodle Demo Seeder

- [ ] Create `cli/seed_moodle_demo.php`.
- [ ] Select evaluation users.
- [ ] Create Moodle users with `username = user_id`.
- [ ] Set Moodle `idnumber = user_id`.
- [ ] Update `local_cr_users.moodle_userid`.
- [ ] Create Moodle course category.
- [ ] Create Moodle courses.
- [ ] Create `local_cr_course_map`.
- [ ] Create enrolment fixtures.
- [ ] Create completion fixtures.
- [ ] Create hidden course fixtures.
- [ ] Reserve unmapped course cases.
- [ ] Make seeder idempotent.

Completion evidence:

- [ ] Moodle users exist.
- [ ] Moodle courses exist.
- [ ] Mapping rows exist.
- [ ] Fixtures exist.

### Step 7: Implement Moodle ML Client

- [ ] Create `local_courserecommender\service\ml_client`.
- [ ] Read settings.
- [ ] Generate request ID.
- [ ] Generate timestamp.
- [ ] Build canonical query string.
- [ ] Sign request with HMAC-SHA256.
- [ ] Add authorization header.
- [ ] Add signature headers.
- [ ] Set timeout.
- [ ] Call export endpoint.
- [ ] Parse HTTP status.
- [ ] Parse JSON.
- [ ] Validate response shape.
- [ ] Handle pagination.
- [ ] Return structured result.
- [ ] Avoid secret logging.

Completion evidence:

- [ ] Client can fetch one page.
- [ ] Client can fetch all pages.
- [ ] Client handles API errors.

### Step 8: Implement Moodle Atomic Sync Service

- [ ] Create `local_courserecommender\service\sync_service`.
- [ ] Create sync run row.
- [ ] Support manual, scheduled, CLI, and fixture run types.
- [ ] Fetch all pages.
- [ ] Validate payload rows.
- [ ] Check user existence.
- [ ] Check Moodle user mapping.
- [ ] Check course mapping.
- [ ] Check Moodle course existence.
- [ ] Check course visibility.
- [ ] Check completion.
- [ ] Check enrolment.
- [ ] Check duplicates.
- [ ] Insert valid rows inactive.
- [ ] Insert skip rows.
- [ ] Count received rows.
- [ ] Count mapped rows.
- [ ] Count displayable rows.
- [ ] Count skipped rows.
- [ ] Store skip reason counts.
- [ ] Activate new rows only after full success.
- [ ] Deactivate previous rows for affected users.
- [ ] Mark sync success.
- [ ] Mark sync failure on critical error.
- [ ] Preserve previous active cache on failure.

Completion evidence:

- [ ] Successful sync creates active recommendations.
- [ ] Failed sync keeps previous active recommendations.
- [ ] Skip reasons are queryable.

### Step 9: Implement Scheduled Task and CLI Sync

- [ ] Implement `classes/task/sync_recommendations.php`.
- [ ] Register scheduled task.
- [ ] Create `cli/sync_recommendations.php`.
- [ ] Support `--mode`.
- [ ] Support `--model-version`.
- [ ] Support `--limit`.
- [ ] Call the same sync service from task and CLI.
- [ ] Print CLI summary.
- [ ] Test Moodle cron execution.

Completion evidence:

- [ ] CLI sync works.
- [ ] Scheduled task works through cron.

### Step 10: Implement Admin Diagnostics

- [ ] Create `diagnostics.php`.
- [ ] Require login.
- [ ] Require diagnostics capability.
- [ ] Show last sync.
- [ ] Show sync status.
- [ ] Show model version.
- [ ] Show active recommendation count.
- [ ] Show stale count.
- [ ] Show total received.
- [ ] Show total mapped.
- [ ] Show total displayable.
- [ ] Show total skipped.
- [ ] Show skip reason counts.
- [ ] Show API latency.
- [ ] Show sync duration.
- [ ] Add manual sync action.
- [ ] Add fixture sync action.
- [ ] Add export action.

Completion evidence:

- [ ] Diagnostics page screenshot.
- [ ] Manual sync can be triggered by admin.
- [ ] Metrics match database counts.

### Step 11: Implement Dashboard Block

- [ ] Find current Moodle user.
- [ ] Match to `local_cr_users.moodle_userid`.
- [ ] Query active recommendations only.
- [ ] Sort by `original_rank`.
- [ ] Limit to top-3.
- [ ] Join with Moodle course data.
- [ ] Display course name.
- [ ] Display score as match percentage.
- [ ] Link to Moodle course page.
- [ ] Show empty state.
- [ ] Show stale state.
- [ ] Never call ML service from block.

Completion evidence:

- [ ] Dashboard screenshot with recommendations.
- [ ] Dashboard screenshot with empty state.
- [ ] Dashboard screenshot with stale state if feasible.

### Step 12: Implement Privacy Providers

- [ ] Implement local plugin privacy provider.
- [ ] Declare stored data in `local_cr_users`.
- [ ] Declare stored data in `local_cr_interactions`.
- [ ] Declare stored data in `local_cr_recommendations`.
- [ ] Declare stored data in `local_cr_rec_skip` if applicable.
- [ ] Declare stored data in `local_cr_eval_results` if applicable.
- [ ] Implement export/delete if feasible for MVP.
- [ ] Implement block null privacy provider if block stores no data.

Completion evidence:

- [ ] Privacy provider exists.
- [ ] Block does not falsely claim ownership of local plugin data.

### Step 13: Implement Evaluation Runner Foundation

- [ ] Create fixture recommendation CSV.
- [ ] Include valid cases.
- [ ] Include unmapped cases.
- [ ] Include hidden cases.
- [ ] Include completed cases.
- [ ] Include already enrolled cases.
- [ ] Include duplicate cases.
- [ ] Include invalid payload cases.
- [ ] Create `cli/run_evaluation.php`.
- [ ] Run fixture sync.
- [ ] Compare expected and actual results.
- [ ] Write `local_cr_eval_results`.
- [ ] Export CSV summary.

Completion evidence:

- [ ] Evaluation runner executes.
- [ ] Results are stored.
- [ ] CSV summary can be exported.

## 4.5 Phase 2 Done Criteria

Phase 2 is done only when:

- [ ] Moodle plugins install.
- [ ] Dataset import works.
- [ ] Demo seeding works.
- [ ] Secure ML client works.
- [ ] Atomic sync works.
- [ ] Skip logging works.
- [ ] Scheduled sync works.
- [ ] CLI sync works.
- [ ] Admin diagnostics works.
- [ ] Dashboard block displays top-3.
- [ ] Dashboard reads cache only.
- [ ] Failure handling works.
- [ ] Privacy provider exists.
- [ ] Evaluation instrumentation exists.

## 5. Phase 3: Post-MVP Agent Todo

## 5.1 Phase Goal

Run formal evaluation, collect evidence, and prepare thesis/paper material from the completed Moodle MVP.

Do not introduce major new MVP functionality in this phase unless evaluation is blocked.

## 5.2 Required Source Documents

Before working on Phase 3, read:

- [ ] `../05_evaluation_plan.md`
- [ ] `../01_final_architecture_design.md`
- [ ] `../02_database_schema.md`
- [ ] `../03_api_contract.md`
- [ ] `implementation_plan.md`, especially Phase 3
- [ ] `detailed_todo.md`, especially Post-MVP Todo

Use `../05_evaluation_plan.md` as the primary source of truth for evaluation.

## 5.3 Deliverables

Produce:

- [ ] Functional evaluation table.
- [ ] Mapping success table.
- [ ] Displayability table.
- [ ] Skip reason count table.
- [ ] Performance result table.
- [ ] Failure handling result table.
- [ ] Security evaluation table.
- [ ] Privacy/logging checklist.
- [ ] Screenshots.
- [ ] Sanitized logs.
- [ ] Evaluation CSV exports.
- [ ] Thesis/paper draft sections.
- [ ] Limitations and future work.

## 5.4 Recommended Execution Order

### Step 1: Freeze MVP for Evaluation

- [ ] Confirm MVP code is stable.
- [ ] Confirm dataset import works.
- [ ] Confirm normal sync works.
- [ ] Confirm fixture sync works.
- [ ] Confirm dashboard works.
- [ ] Confirm diagnostics page works.
- [ ] Avoid unrelated refactors during evaluation.

Completion evidence:

- [ ] Stable MVP run summary.
- [ ] Known configuration documented.

### Step 2: Run Functional Evaluation

- [ ] Run dataset import.
- [ ] Run Moodle demo seeding.
- [ ] Run normal sync.
- [ ] Run fixture sync.
- [ ] Test valid recommendation display.
- [ ] Test unmapped course skip.
- [ ] Test hidden course skip.
- [ ] Test completed course skip.
- [ ] Test already enrolled skip.
- [ ] Test duplicate recommendation skip.
- [ ] Test invalid payload skip.
- [ ] Test empty state.
- [ ] Test stale state.
- [ ] Calculate functional pass rate.

Completion evidence:

- [ ] Functional result table.
- [ ] Pass/fail evidence.

### Step 3: Run Mapping Evaluation

- [ ] Export total recommendations received.
- [ ] Export mapped recommendation count.
- [ ] Export unmapped recommendation count.
- [ ] Calculate mapping success rate.
- [ ] Explain unmapped cases.

Completion evidence:

- [ ] Mapping result table.
- [ ] Mapping formula shown.

### Step 4: Run Displayability Evaluation

- [ ] Export total displayable recommendations.
- [ ] Export total skipped recommendations.
- [ ] Group skips by reason.
- [ ] Calculate displayable recommendation rate.
- [ ] Explain major skip reasons.

Completion evidence:

- [ ] Displayability result table.
- [ ] Skip reason count table.

### Step 5: Run Performance Evaluation

- [ ] Measure ML export API latency.
- [ ] Measure sync duration.
- [ ] Measure dashboard render time from cache.
- [ ] Repeat measurements multiple times.
- [ ] Calculate average.
- [ ] Calculate minimum.
- [ ] Calculate maximum.
- [ ] Compare against target.

Completion evidence:

- [ ] Performance table.
- [ ] Measurement method documented.

### Step 6: Run Failure Handling Evaluation

- [ ] Test ML service unavailable.
- [ ] Test timeout.
- [ ] Test HTTP 500.
- [ ] Test malformed JSON.
- [ ] Test missing required fields.
- [ ] Confirm sync fails safely.
- [ ] Confirm previous cache remains active.
- [ ] Confirm dashboard still loads.

Completion evidence:

- [ ] Failure handling table.
- [ ] Before/after active cache count.
- [ ] Dashboard screenshot after failure.

### Step 7: Run Security Evaluation

- [ ] Test valid request.
- [ ] Test missing API key.
- [ ] Test invalid API key.
- [ ] Test missing signature.
- [ ] Test invalid signature.
- [ ] Test expired timestamp.
- [ ] Test modified signed request.
- [ ] Check source for hardcoded secrets.
- [ ] Check logs for exposed secrets.

Completion evidence:

- [ ] Security result table.
- [ ] Sanitized log sample.

### Step 8: Run Privacy and Logging Evaluation

- [ ] Verify local privacy provider.
- [ ] Verify block privacy provider.
- [ ] Verify stored user data is declared.
- [ ] Verify secrets are not exported.
- [ ] Verify logs are sanitized.
- [ ] Test export/delete if implemented.

Completion evidence:

- [ ] Privacy/logging checklist.

### Step 9: Collect Evidence Package

- [ ] Architecture diagram.
- [ ] Database schema diagram.
- [ ] API contract summary.
- [ ] Dashboard screenshot.
- [ ] Admin diagnostics screenshot.
- [ ] Sync log export.
- [ ] Skip reason export.
- [ ] Evaluation CSV.
- [ ] Security test evidence.
- [ ] Pre-MVP ML quality results.

Completion evidence:

- [ ] Evidence folder organized by topic.

### Step 10: Draft Thesis/Paper Sections

- [ ] Write introduction.
- [ ] Write problem statement.
- [ ] Write dataset section.
- [ ] Write architecture section.
- [ ] Write Pre-MVP simulator section.
- [ ] Write ML service section.
- [ ] Write Moodle integration section.
- [ ] Write security section.
- [ ] Write implementation section.
- [ ] Write evaluation method.
- [ ] Write evaluation results.
- [ ] Write discussion.
- [ ] Write limitations.
- [ ] Write conclusion.
- [ ] Write future work.

Completion evidence:

- [ ] Draft text exists.
- [ ] Tables and screenshots are referenced.

## 5.5 Phase 3 Done Criteria

Phase 3 is done only when:

- [ ] Evaluation results are complete.
- [ ] Evidence package is complete.
- [ ] Logs are sanitized.
- [ ] Screenshots are collected.
- [ ] Thesis/paper draft sections exist.
- [ ] Limitations are clear.
- [ ] Future work is separated from MVP claims.

## 6. Agent Reporting Format

At the end of each implementation session, report:

```text
Completed:
- ...

Changed files:
- ...

Verification:
- ...

Blocked:
- ...

Next recommended step:
- ...
```

If a test cannot be run, state why.

If a source-of-truth document conflicts with implementation reality, stop and document the conflict before changing the architecture.

