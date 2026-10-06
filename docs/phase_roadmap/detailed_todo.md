# CRE Detailed Todo Checklist

## 1. Pre-MVP Todo

## 1.1 Planning and Scope

- [ ] Define Pre-MVP as "ML service plus PHP LMS simulator", not Moodle.
- [ ] Write a short Pre-MVP goal statement.
- [ ] Decide the minimum demo scenario for professor review.
- [ ] Decide the ML quality metrics to report.
- [ ] Decide the security tests to demonstrate.
- [ ] Confirm that Moodle is intentionally excluded from Pre-MVP.
- [ ] Confirm that the same API contract will be reused in the Moodle MVP.
- [ ] Confirm that `user_id` and `canonical_course_id` are strings everywhere.

## 1.2 Dataset Preparation

- [ ] Collect cleaned dataset files.
- [ ] Verify `users.csv` exists.
- [ ] Verify `courses.csv` exists.
- [ ] Verify `course_alias_map.csv` exists.
- [ ] Verify `interactions.csv` exists.
- [ ] Check row counts for every file.
- [ ] Check required columns in `users.csv`.
- [ ] Check required columns in `courses.csv`.
- [ ] Check required columns in `course_alias_map.csv`.
- [ ] Check required columns in `interactions.csv`.
- [ ] Verify that `user_id` values preserve leading zeros.
- [ ] Verify that `canonical_course_id` values are consistent across files.
- [ ] Verify that interaction types are normalized.
- [ ] Identify missing or duplicate course IDs.
- [ ] Identify users with no interactions.
- [ ] Identify high-activity users.
- [ ] Identify medium-activity users.
- [ ] Identify sparse users.
- [ ] Identify users with certified interactions.
- [ ] Save dataset validation summary.

## 1.3 ML Model Preparation

- [ ] Choose baseline recommendation approach.
- [ ] Define training data input.
- [ ] Define evaluation split.
- [ ] Train or run recommendation generation.
- [ ] Generate top-K recommendations per user.
- [ ] Use top-20 candidates per user for integration testing.
- [ ] Store generated recommendations in a reproducible format.
- [ ] Include `user_id` in output.
- [ ] Include `canonical_course_id` in output.
- [ ] Include `rank` in output.
- [ ] Include `score` in output.
- [ ] Include `model_version` in output.
- [ ] Include `generated_at` in output.
- [ ] Confirm no Moodle internal IDs appear in ML output.
- [ ] Confirm no course name is used as identifier.
- [ ] Create a small deterministic test fixture output.

## 1.4 ML Quality Evaluation

- [ ] Define ground truth evaluation method.
- [ ] Calculate Precision@3.
- [ ] Calculate Hit Rate@3.
- [ ] Calculate NDCG@3.
- [ ] Add Precision@5 if useful.
- [ ] Compare against a simple baseline if available.
- [ ] Prepare sample recommendations for selected users.
- [ ] Review recommendations manually for sanity.
- [ ] Document limitations of ML quality evaluation.
- [ ] Store ML evaluation result table.
- [ ] Prepare ML quality summary for professor demo.

## 1.5 ML Recommendation Service

- [ ] Choose service framework.
- [ ] Create service project structure.
- [ ] Add configuration loading.
- [ ] Add recommendation data loader.
- [ ] Add model version configuration.
- [ ] Add generated timestamp handling.
- [ ] Implement `GET /recommendations/export`.
- [ ] Implement `limit` query parameter.
- [ ] Enforce maximum `limit = 1000`.
- [ ] Implement cursor pagination.
- [ ] Make cursor opaque to client.
- [ ] Ensure stable ordering during export.
- [ ] Add `page.has_more`.
- [ ] Add `page.next_cursor`.
- [ ] Implement optional `GET /recommendations/user/{user_id}`.
- [ ] Add test mode or fixture mode.
- [ ] Return JSON response with required fields.
- [ ] Return structured error response.
- [ ] Add request ID to responses.
- [ ] Add health check endpoint if useful.

## 1.6 Pre-MVP API Security

- [ ] Define API key or bearer token format.
- [ ] Store API secret outside source code.
- [ ] Require `Authorization` header.
- [ ] Require `X-Request-Id` header.
- [ ] Require `X-Timestamp` header.
- [ ] Require `X-Signature` header.
- [ ] Define HMAC canonical string.
- [ ] Implement HMAC-SHA256 signing verification.
- [ ] Implement timestamp expiry window.
- [ ] Use constant-time signature comparison.
- [ ] Reject missing API key.
- [ ] Reject invalid API key.
- [ ] Reject missing signature.
- [ ] Reject invalid signature.
- [ ] Reject expired timestamp.
- [ ] Return clear error codes.
- [ ] Mask secrets in logs.
- [ ] Avoid logging raw sensitive payloads.
- [ ] Add security test cases.

## 1.7 PHP LMS Simulator Schema

- [ ] Choose database for simulator.
- [ ] Create `sim_users`.
- [ ] Create `sim_courses`.
- [ ] Create `sim_course_alias` if needed.
- [ ] Create `sim_interactions` if needed.
- [ ] Create `sim_course_map`.
- [ ] Create `sim_sync_runs`.
- [ ] Create `sim_recommendations`.
- [ ] Create `sim_rec_skip`.
- [ ] Create `sim_security_logs`.
- [ ] Create `sim_model_eval_results` if useful.
- [ ] Add unique index on `sim_users.user_id`.
- [ ] Add unique index on `sim_courses.canonical_course_id`.
- [ ] Add unique index on `sim_course_map.canonical_course_id`.
- [ ] Add index on `sim_recommendations(user_id, is_active)`.
- [ ] Add index on `sim_recommendations(sync_run_id)`.
- [ ] Add index on `sim_rec_skip(sync_run_id)`.
- [ ] Add index on `sim_rec_skip(skip_reason)`.

## 1.8 PHP LMS Simulator Data Import

- [ ] Build dataset import command or page.
- [ ] Import users.
- [ ] Import courses.
- [ ] Import course aliases if needed.
- [ ] Import interactions if needed.
- [ ] Preserve `user_id` leading zeros.
- [ ] Preserve `canonical_course_id` as string.
- [ ] Make import idempotent.
- [ ] Print import summary.
- [ ] Store import error details.
- [ ] Create local course records.
- [ ] Create course mappings.
- [ ] Reserve some unmapped courses for testing.
- [ ] Mark some courses hidden for testing.
- [ ] Mark some user-course pairs completed for testing.
- [ ] Mark some user-course pairs already enrolled for testing.

## 1.9 PHP LMS Simulator Sync

- [ ] Build ML API client.
- [ ] Build request signer.
- [ ] Add HTTP timeout.
- [ ] Create sync run record.
- [ ] Fetch first export page.
- [ ] Loop through all export pages.
- [ ] Validate response JSON.
- [ ] Validate `user_id`.
- [ ] Validate `canonical_course_id`.
- [ ] Validate `rank`.
- [ ] Validate `score`.
- [ ] Detect duplicate user-course rows in a sync run.
- [ ] Map canonical course ID to simulator course ID.
- [ ] Check course exists.
- [ ] Check course visibility.
- [ ] Check completion status.
- [ ] Check enrolment status.
- [ ] Insert valid recommendation rows as inactive.
- [ ] Insert skipped rows with reason.
- [ ] Update sync counters.
- [ ] Activate new rows after full success.
- [ ] Keep old active cache after failure.
- [ ] Mark sync run success.
- [ ] Mark sync run failed on error.
- [ ] Print sync summary.

## 1.10 PHP LMS Simulator Dashboard

- [ ] Build simple user selector or login.
- [ ] Build dashboard page.
- [ ] Load active recommendations for selected user.
- [ ] Sort by original rank.
- [ ] Display top-3 recommendations.
- [ ] Show course name.
- [ ] Show score as match percentage.
- [ ] Link to simulated course detail page.
- [ ] Show empty state.
- [ ] Show stale state.
- [ ] Avoid fake reason text if reason is null.
- [ ] Show last updated timestamp.

## 1.11 PHP LMS Simulator Admin/Debug Page

- [ ] Show last sync status.
- [ ] Show model version.
- [ ] Show total received.
- [ ] Show total mapped.
- [ ] Show total displayable.
- [ ] Show total skipped.
- [ ] Show skip reason counts.
- [ ] Show API latency.
- [ ] Show sync duration.
- [ ] Add manual sync action.
- [ ] Add fixture sync action.
- [ ] Add security test result summary.
- [ ] Add export CSV action if useful.

## 1.12 Pre-MVP Security Testing

- [ ] Test valid request.
- [ ] Test missing API key.
- [ ] Test invalid API key.
- [ ] Test missing request ID.
- [ ] Test missing timestamp.
- [ ] Test expired timestamp.
- [ ] Test missing signature.
- [ ] Test invalid signature.
- [ ] Test modified query string after signing.
- [ ] Test modified body after signing if any POST endpoint exists.
- [ ] Test service timeout.
- [ ] Test malformed JSON.
- [ ] Test HTTP 500 response.
- [ ] Confirm old cache remains after failed sync.
- [ ] Confirm secrets are not logged.
- [ ] Save security test evidence.

## 1.13 Pre-MVP Demo Preparation

- [ ] Prepare one normal recommendation demo user.
- [ ] Prepare one unmapped-course demo case.
- [ ] Prepare one hidden-course demo case.
- [ ] Prepare one completed-course demo case.
- [ ] Prepare one already-enrolled demo case.
- [ ] Prepare one ML failure demo.
- [ ] Prepare one invalid-signature demo.
- [ ] Prepare screenshots.
- [ ] Prepare short explanation of architecture.
- [ ] Prepare short explanation of security.
- [ ] Prepare short explanation of ML metrics.

## 1.14 Pre-MVP Exit Checklist

- [ ] ML service runs.
- [ ] Export API works.
- [ ] PHP simulator runs.
- [ ] Simulator imports real dataset.
- [ ] Simulator syncs from ML service.
- [ ] Simulator validates and maps courses.
- [ ] Simulator caches recommendations.
- [ ] Simulator displays top-3.
- [ ] Invalid recommendations are skipped and logged.
- [ ] Security tests pass.
- [ ] ML quality metrics are available.
- [ ] Professor demo is ready.

## 2. MVP for Skripsi Todo

## 2.1 Moodle Environment

- [ ] Install Moodle 5.x local environment.
- [ ] Configure database.
- [ ] Configure PHP settings.
- [ ] Configure cron for local testing.
- [ ] Confirm plugin development mode.
- [ ] Confirm debugging settings.
- [ ] Confirm admin user access.
- [ ] Create plugin development workspace.

## 2.2 `local_courserecommender` Skeleton

- [ ] Create plugin directory.
- [ ] Add `version.php`.
- [ ] Add language strings.
- [ ] Add `settings.php`.
- [ ] Add `db/install.xml`.
- [ ] Add `db/access.php`.
- [ ] Add `db/tasks.php`.
- [ ] Add `classes/privacy/provider.php`.
- [ ] Add `classes/task/sync_recommendations.php`.
- [ ] Add `classes/service` directory.
- [ ] Add `cli` directory.
- [ ] Add diagnostics page placeholder.
- [ ] Install plugin in Moodle.
- [ ] Verify plugin appears in site administration.

## 2.3 `block_courserecommender` Skeleton

- [ ] Create block plugin directory.
- [ ] Add `version.php`.
- [ ] Add language strings.
- [ ] Add main block class.
- [ ] Add renderer or output class if needed.
- [ ] Add styles if needed.
- [ ] Add null privacy provider.
- [ ] Install block plugin.
- [ ] Add block to dashboard.
- [ ] Confirm empty state renders.

## 2.4 Moodle Database Tables

- [ ] Implement `local_cr_users`.
- [ ] Implement `local_cr_courses`.
- [ ] Implement `local_cr_course_alias`.
- [ ] Implement `local_cr_interactions`.
- [ ] Implement `local_cr_course_map`.
- [ ] Implement `local_cr_sync_runs`.
- [ ] Implement `local_cr_recommendations`.
- [ ] Implement `local_cr_rec_skip`.
- [ ] Implement `local_cr_eval_results`.
- [ ] Add unique index for `local_cr_users.user_id`.
- [ ] Add unique index for `local_cr_courses.canonical_course_id`.
- [ ] Add unique index for `local_cr_course_map.canonical_course_id`.
- [ ] Add recommendation cache indexes.
- [ ] Add skip log indexes.
- [ ] Validate install XML.
- [ ] Reinstall or upgrade plugin cleanly.

## 2.5 Moodle Capabilities and Permissions

- [ ] Define `local/courserecommender:viewdiagnostics`.
- [ ] Define `local/courserecommender:runsync`.
- [ ] Define `local/courserecommender:exportlogs`.
- [ ] Assign capabilities to site admin by default.
- [ ] Protect diagnostics page with `require_login`.
- [ ] Protect diagnostics page with capability check.
- [ ] Protect manual sync action.
- [ ] Protect log export action.

## 2.6 Moodle Admin Settings

- [ ] Add ML service base URL setting.
- [ ] Add API key setting.
- [ ] Add HMAC secret setting or environment variable reference.
- [ ] Add timeout setting.
- [ ] Add stale threshold setting.
- [ ] Add default page limit setting.
- [ ] Add model version setting.
- [ ] Add fixture mode setting if useful.
- [ ] Ensure secrets are not displayed back plainly.
- [ ] Ensure settings validation is reasonable.

## 2.7 Moodle Dataset Import CLI

- [ ] Create `cli/seed_dataset.php`.
- [ ] Add `--data-dir` option.
- [ ] Read `users.csv`.
- [ ] Read `courses.csv`.
- [ ] Read `course_alias_map.csv`.
- [ ] Read `interactions.csv`.
- [ ] Preserve leading zeros in `user_id`.
- [ ] Store `canonical_course_id` as string.
- [ ] Upsert users.
- [ ] Upsert courses.
- [ ] Upsert aliases.
- [ ] Upsert interactions.
- [ ] Validate required columns.
- [ ] Print row counts.
- [ ] Print skipped row counts.
- [ ] Make import idempotent.
- [ ] Add error handling.

## 2.8 Moodle Demo Seeder

- [ ] Create `cli/seed_moodle_demo.php`.
- [ ] Select evaluation users.
- [ ] Create Moodle users with `username = user_id`.
- [ ] Set Moodle `idnumber = user_id`.
- [ ] Update `local_cr_users.moodle_userid`.
- [ ] Create Moodle course category if needed.
- [ ] Create Moodle courses from canonical courses.
- [ ] Create `local_cr_course_map` rows.
- [ ] Create selected enrolment fixtures.
- [ ] Create selected completion fixtures.
- [ ] Create selected hidden course fixtures.
- [ ] Reserve unmapped course fixtures.
- [ ] Print created user count.
- [ ] Print created course count.
- [ ] Print mapping count.
- [ ] Make seeder idempotent.

## 2.9 Moodle Setup Wrapper

- [ ] Create `cli/setup_demo.php`.
- [ ] Run dataset import.
- [ ] Run Moodle demo seeder.
- [ ] Optionally run fixture sync.
- [ ] Print final setup summary.
- [ ] Print next commands.

## 2.10 Moodle ML Client

- [ ] Create `local_courserecommender\service\ml_client`.
- [ ] Load settings.
- [ ] Build export endpoint URL.
- [ ] Build canonical query string.
- [ ] Generate request ID.
- [ ] Generate timestamp.
- [ ] Generate HMAC signature.
- [ ] Add authorization header.
- [ ] Add request ID header.
- [ ] Add timestamp header.
- [ ] Add signature header.
- [ ] Set HTTP timeout.
- [ ] Send GET request.
- [ ] Parse HTTP status.
- [ ] Parse JSON body.
- [ ] Validate required top-level fields.
- [ ] Validate page object.
- [ ] Validate recommendations array.
- [ ] Return typed result.
- [ ] Handle network errors.
- [ ] Handle timeout errors.
- [ ] Avoid logging secrets.

## 2.11 Moodle Sync Service

- [ ] Create `local_courserecommender\service\sync_service`.
- [ ] Create sync run row.
- [ ] Support run types: scheduled, manual, fixture, cli.
- [ ] Fetch first recommendation page.
- [ ] Process pagination until complete.
- [ ] Validate every row.
- [ ] Check user exists in `local_cr_users`.
- [ ] Check `moodle_userid` exists.
- [ ] Check course mapping exists.
- [ ] Check Moodle course exists.
- [ ] Check Moodle course visible.
- [ ] Check user has not completed course.
- [ ] Check user is not already enrolled.
- [ ] Check duplicate recommendation.
- [ ] Insert valid recommendation as inactive.
- [ ] Insert skip log row.
- [ ] Track total received.
- [ ] Track total mapped.
- [ ] Track total displayable.
- [ ] Track total skipped.
- [ ] Track skip reason counts.
- [ ] Track API latency.
- [ ] Track sync duration.
- [ ] Activate new recommendations after success.
- [ ] Deactivate old rows for affected users.
- [ ] Mark sync success.
- [ ] Mark sync failed on critical error.
- [ ] Keep previous active rows after failure.
- [ ] Clean up pending rows if needed.

## 2.12 Moodle Scheduled Task and CLI

- [ ] Implement scheduled task class.
- [ ] Register scheduled task in `db/tasks.php`.
- [ ] Configure daily schedule after ML batch.
- [ ] Create `cli/sync_recommendations.php`.
- [ ] Add `--mode=normal|fixture` option.
- [ ] Add `--model-version=latest` option.
- [ ] Add `--limit=1000` option.
- [ ] Call same sync service from task and CLI.
- [ ] Print sync summary in CLI.
- [ ] Test manual CLI sync.
- [ ] Test scheduled task through Moodle cron.

## 2.13 Moodle Admin Diagnostics

- [ ] Create `diagnostics.php`.
- [ ] Add capability protection.
- [ ] Show last sync status.
- [ ] Show model version.
- [ ] Show active recommendation count.
- [ ] Show stale recommendation count.
- [ ] Show total received.
- [ ] Show total mapped.
- [ ] Show total displayable.
- [ ] Show total skipped.
- [ ] Show skip reason counts.
- [ ] Show API latency.
- [ ] Show sync duration.
- [ ] Add test connection action.
- [ ] Add manual sync action.
- [ ] Add fixture sync action.
- [ ] Add export evaluation CSV action.
- [ ] Keep business logic in service classes.

## 2.14 Moodle Dashboard Block

- [ ] Find current Moodle user.
- [ ] Find matching `local_cr_users` by `moodle_userid`.
- [ ] Query active recommendations.
- [ ] Join Moodle course data.
- [ ] Sort by `original_rank`.
- [ ] Limit to top-3.
- [ ] Display course name.
- [ ] Display score as match percentage.
- [ ] Link to Moodle course page.
- [ ] Show empty state if no recommendations.
- [ ] Show stale state if older than threshold.
- [ ] Hide score if score is missing.
- [ ] Avoid fake reason text.
- [ ] Confirm block never calls ML API.
- [ ] Test dashboard render time.

## 2.15 Moodle Privacy Providers

- [ ] Implement local plugin privacy provider.
- [ ] Declare stored user-related data.
- [ ] Include `local_cr_users`.
- [ ] Include `local_cr_interactions`.
- [ ] Include `local_cr_recommendations`.
- [ ] Include `local_cr_rec_skip` if user ID is stored.
- [ ] Include `local_cr_eval_results` if user ID is stored.
- [ ] Implement export if feasible.
- [ ] Implement delete/anonymize if feasible.
- [ ] Implement block null privacy provider.
- [ ] Verify privacy provider does not falsely claim no local data.

## 2.16 Moodle Fixture Evaluation Foundation

- [ ] Create recommendation fixture CSV.
- [ ] Include valid recommendation cases.
- [ ] Include unmapped course cases.
- [ ] Include hidden course cases.
- [ ] Include completed course cases.
- [ ] Include already enrolled cases.
- [ ] Include duplicate recommendation cases.
- [ ] Include invalid rank cases.
- [ ] Include invalid score cases.
- [ ] Include no recommendation users.
- [ ] Create `cli/run_evaluation.php`.
- [ ] Run fixture sync.
- [ ] Compare expected result with actual result.
- [ ] Write `local_cr_eval_results`.
- [ ] Print pass/fail summary.
- [ ] Export CSV summary.

## 2.17 MVP Security Testing

- [ ] Test valid Moodle sync request.
- [ ] Test missing API key.
- [ ] Test invalid API key.
- [ ] Test missing HMAC signature.
- [ ] Test invalid HMAC signature.
- [ ] Test expired timestamp.
- [ ] Test ML service unavailable.
- [ ] Test timeout.
- [ ] Test malformed JSON.
- [ ] Confirm dashboard still loads after failure.
- [ ] Confirm previous active cache remains.
- [ ] Confirm secrets are not logged.
- [ ] Confirm no hardcoded secrets in source.

## 2.18 MVP Exit Checklist

- [ ] Plugins install successfully.
- [ ] Dataset import works.
- [ ] Moodle demo seed works.
- [ ] Course mapping works.
- [ ] ML client works.
- [ ] Sync service works.
- [ ] Atomic activation works.
- [ ] Skip logging works.
- [ ] Scheduled task works.
- [ ] CLI sync works.
- [ ] Admin diagnostics works.
- [ ] Dashboard block works.
- [ ] Empty state works.
- [ ] Stale state works.
- [ ] Failure handling works.
- [ ] Basic security tests pass.
- [ ] Evaluation instrumentation exists.

## 3. Post-MVP Todo

## 3.1 Evaluation Planning

- [ ] Freeze MVP code for evaluation.
- [ ] Define final evaluation dataset.
- [ ] Define final Moodle evaluation subset.
- [ ] Define final test fixture set.
- [ ] Define number of performance test runs.
- [ ] Define screenshots needed.
- [ ] Define log exports needed.
- [ ] Define table formats for thesis/paper.

## 3.2 Functional Evaluation

- [ ] Run dataset import test.
- [ ] Run Moodle demo seeding test.
- [ ] Run normal sync test.
- [ ] Run fixture sync test.
- [ ] Test valid recommendations.
- [ ] Test unmapped course handling.
- [ ] Test hidden course handling.
- [ ] Test completed course handling.
- [ ] Test already enrolled handling.
- [ ] Test duplicate recommendation handling.
- [ ] Test invalid payload handling.
- [ ] Test no recommendation empty state.
- [ ] Test stale cache state.
- [ ] Test dashboard top-3 display.
- [ ] Calculate functional pass rate.
- [ ] Export functional result table.

## 3.3 Mapping Evaluation

- [ ] Run normal recommendation sync.
- [ ] Export total recommendation rows received.
- [ ] Export mapped recommendation count.
- [ ] Export unmapped recommendation count.
- [ ] Calculate mapping success rate.
- [ ] Create mapping result table.
- [ ] Explain causes of unmapped rows.

## 3.4 Displayability Evaluation

- [ ] Export displayable recommendation count.
- [ ] Export skipped recommendation count.
- [ ] Group skip rows by reason.
- [ ] Calculate displayable recommendation rate.
- [ ] Create skip reason count table.
- [ ] Explain why courses were filtered.
- [ ] Confirm filtering matches system rules.

## 3.5 Performance Evaluation

- [ ] Measure ML export API latency.
- [ ] Measure Moodle sync duration.
- [ ] Measure validation/mapping time if available.
- [ ] Measure dashboard render time from cache.
- [ ] Run each test multiple times.
- [ ] Record average.
- [ ] Record minimum.
- [ ] Record maximum.
- [ ] Compare dashboard render time with target.
- [ ] Compare API timeout behavior with target.
- [ ] Create performance result table.

## 3.6 Failure Handling Evaluation

- [ ] Test ML service unavailable.
- [ ] Test endpoint timeout.
- [ ] Test HTTP 500 response.
- [ ] Test malformed JSON.
- [ ] Test missing required fields.
- [ ] Test invalid rank.
- [ ] Test invalid score.
- [ ] Confirm sync run is marked failed.
- [ ] Confirm error is logged.
- [ ] Confirm pending rows are not activated.
- [ ] Confirm old active cache remains.
- [ ] Confirm dashboard still loads.
- [ ] Capture evidence before and after failure.
- [ ] Create failure handling result table.

## 3.7 Security Evaluation

- [ ] Test valid request accepted.
- [ ] Test missing API key rejected.
- [ ] Test invalid API key rejected.
- [ ] Test missing signature rejected.
- [ ] Test invalid signature rejected.
- [ ] Test expired timestamp rejected.
- [ ] Test modified signed request rejected.
- [ ] Check logs for raw secrets.
- [ ] Check source code for hardcoded API secrets.
- [ ] Check operational logs for excessive personal data.
- [ ] Create security evaluation table.
- [ ] Write security design explanation.

## 3.8 Privacy and Logging Evaluation

- [ ] Verify local plugin privacy provider exists.
- [ ] Verify block privacy provider exists.
- [ ] Verify user-related tables are declared.
- [ ] Test user data export if implemented.
- [ ] Test user data deletion/anonymization if implemented.
- [ ] Verify API key is not exported.
- [ ] Verify HMAC secret is not exported.
- [ ] Verify logs are sanitized.
- [ ] Create privacy/logging checklist.

## 3.9 ML Quality Reporting

- [ ] Bring Pre-MVP ML quality results into final report.
- [ ] Report Precision@3.
- [ ] Report Hit Rate@3.
- [ ] Report NDCG@3.
- [ ] Report baseline comparison if available.
- [ ] Report limitations of ML evaluation.
- [ ] State that ML quality is supporting evidence.
- [ ] Keep Moodle integration as the primary contribution.

## 3.10 Evidence Collection

- [ ] Capture architecture diagram.
- [ ] Capture database schema diagram.
- [ ] Capture API contract summary.
- [ ] Capture ML service screenshot or logs.
- [ ] Capture PHP simulator screenshots if useful as Pre-MVP evidence.
- [ ] Capture Moodle dashboard screenshot.
- [ ] Capture Moodle admin diagnostics screenshot.
- [ ] Export sync logs.
- [ ] Export skip reason logs.
- [ ] Export evaluation CSV.
- [ ] Export security test results.
- [ ] Store sanitized logs.
- [ ] Organize evidence by chapter or paper section.

## 3.11 Thesis/Paper Writing

- [ ] Write introduction.
- [ ] Write problem statement.
- [ ] Write research scope.
- [ ] Write related work.
- [ ] Write dataset description.
- [ ] Write Pre-MVP simulator explanation.
- [ ] Write ML service overview.
- [ ] Write Moodle integration architecture.
- [ ] Write database design.
- [ ] Write API contract.
- [ ] Write security design.
- [ ] Write implementation chapter.
- [ ] Write evaluation method.
- [ ] Write functional evaluation results.
- [ ] Write mapping evaluation results.
- [ ] Write displayability evaluation results.
- [ ] Write performance evaluation results.
- [ ] Write failure handling results.
- [ ] Write security evaluation results.
- [ ] Write discussion.
- [ ] Write limitations.
- [ ] Write conclusion.
- [ ] Write future work.

## 3.12 Optional Hardening

- [ ] Add Docker setup.
- [ ] Add local deployment script.
- [ ] Add CI checks.
- [ ] Add automated unit tests.
- [ ] Add more integration tests.
- [ ] Improve admin diagnostics UI.
- [ ] Add sync history browser.
- [ ] Add mapping editor.
- [ ] Add monitoring endpoint.
- [ ] Add structured logs.
- [ ] Add secret rotation documentation.
- [ ] Add production deployment notes.

## 3.13 Post-MVP Exit Checklist

- [ ] Functional evaluation table completed.
- [ ] Mapping evaluation table completed.
- [ ] Displayability evaluation table completed.
- [ ] Performance evaluation table completed.
- [ ] Failure handling table completed.
- [ ] Security evaluation table completed.
- [ ] Privacy/logging checklist completed.
- [ ] Screenshots collected.
- [ ] Sanitized logs exported.
- [ ] Evaluation CSV exported.
- [ ] Thesis/paper draft completed.
- [ ] Limitations documented.
- [ ] Future work documented.
- [ ] Final demo is ready.

