# Can a model change credibly raise Hit@10? Improvement study (x1), 2026-10-04

Scope: data contract asserted in every run (`assert_contract(raw=True)` PASS); nothing in `common/`, `results/e*` or `logs/e*` was touched.
All new code is in `experiments_new/`, all outputs are tagged `x1_*`. Design selection used the VALIDATION target only.

## Bottom line (read this first)
1. **No model change gives a credible, protocol-robust gain in Hit@10.** The best candidate (SASRec + calendar-month embedding, "C_calendar") adds about +1.0 pt on validation, but
   the gain exists only because the per-user split lets the model see what other users enrolled in during the same calendar period. Under a forward-in-time split it vanishes (+0.5 pt, within noise).
2. **Attention is not the lever and no attention variant was found that is.** Gap/time-interval information (the input needed by TiSASRec-style attention) gave +0.0 pt. Competency/level auxiliary loss, label smoothing, cropping augmentation, longer training and Markov/LSTM hybrids all gave 0 or negative.
3. **The headline Hit@10 is inflated by one trivially predictable cohort.** 27.3 % of test users (1,242 of 4,553) follow the identical curriculum 46 -> 47 -> 21 -> 52 -> 60 and every model scores about 99.9 % on them. On the other 72.7 % the models score 0.90 (default) / 0.85 (strict), and that is where all differences live.
4. **A forward-chaining audit shows Hit@10 drops to about 0.51** when only the past is used for training and the future is evaluated (validation users, 5 seeds). This is the most important finding for the paper's validity, and also the most defensible new contribution (evaluation, not architecture).
5. **Recommendation:** do not claim novelty from attention or from an improved architecture. Reframe the contribution as a protocol-aware, cohort-aware comparative evaluation (strict protocol, cohort-excluded metrics, forward-time audit, honest null result for attention). If the authors still want a model row, report C_calendar only as an explicitly protocol-dependent finding (command in section 6).

## 1. Headroom diagnosis (Task A)
Only top-10 lists and per-user hit/rank arrays are stored (no scores), so score-level ensembling could not be computed from saved files; it was re-trained and tested in section 3 (validation). Rank-level aggregation of the saved top-10 lists is given as an approximation. Test per-user files were used only descriptively (no selection).

| Quantity (test, 10 seeds) | default | strict |
|---|---|---|
| SASRec / LSTM-attn / GRU / Markov Hit@10, all users | .9282 / .9235 / .9242 / .8669 | .8909 / .8821 / .8811 / .5511 |
| same, cohort users (n=1,242, history 46-47-21, target course 60) | .9996 / 1.000 / .9996 / 1.000 | .9993 / .9989 / .9991 / .0016 |
| same, **non-cohort users** (n=3,311 / 3,309) | **.9015 / .8948 / .8959 / .8170** | **.8502 / .8383 / .8367 / .7573** |
| random among unmasked candidates (about 52 left) | .197 | .193 |
| users missed by ALL 5 model families x 10 seeds (oracle) | 1.8 % | 3.5 % |
| users whose hit flips between seeds (SASRec) / always miss | 6.4 % / 4.4 % | 9.1 % / 6.8 % |
| rank-aggregating saved top-10 lists: SASRec x10 / LSTM x10 / SAS+LSTM / all five | .9310 / .9306 / .9337 / .9343 | .8965 / .8956 / .8974 / .8958 |

- **Where models fail:** by history length the worst groups are 5-10 courses (0.85-0.88 default); the 4-course group (the cohort) is 0.977. Failure is not tied to rare courses (only 4.9 % of non-cohort targets have train frequency < 100). Ten target courses account for 48-50 % of all SASRec misses (courses 4-8, 15, 18, 38, 45, 55).
- **Misses are near-misses.** Validation, non-cohort, 5-seed mean probability (SASRec): Hit@5 .809, Hit@10 .916, Hit@20 .981, Hit@30 .996. Of the 8.4 % misses, 4.4 % sit at rank 11-15 (median miss rank 15), 2.1 % at 16-20 and only 1.9 % beyond 20.
- **Realistic ceiling:** the 1.8 % (default) never-hit users bound the achievable Hit@10 near 0.98 only under an oracle over 50 models; a single deployable model is realistically capped at roughly 0.93-0.95 default / 0.89-0.91 strict. Seed noise alone moves a user's outcome for 6-9 % of users, so differences below about 0.3 pt are not interpretable.
- **Default vs strict:** strict is a skip-one task. Markov collapses on the cohort in strict (Hit@10 .0016) while neural models keep .999 because they learn the 2-step pattern; this is the whole neural-vs-Markov gap in strict (non-cohort gap is 0.09, not 0.33).
- **Explains the earlier anomaly:** `sasrec_full_features` seed 89 (strict Hit@10 .619) failed on exactly the cohort: 1,299 of 1,610 strict users with history length 3 missed, of whom 1,240 had target course 60 and top-1 52. In normal runs course 60 sits inside the top-10 behind 52; in the collapsed run it fell out. I reproduced this mechanism in new runs (below).
- **Timestamps exist and are informative.** Enrolments come in mass events (three timestamps carry about 1,680 users each); 40.6 % of test targets are courses first seen in train after the user's last history timestamp; median gap from last history item to target is 11.9 days.

## 2. What was tried (validation only; Task B). Code: `xlib.py`, `x1_ablation.py`
Base = SASRec d=96, 2 blocks, 2 heads, dropout .2 (the e4 configuration, re-implemented, "S0_base"). Same recipe as e4. Val = default-like validation target; vstrict = skip-one validation analogue of the strict protocol (history = train core minus last course; 4,221 of 4,601 users, directional only).
Same-seed GPU re-runs differ by up to 0.5 pt (S0_base val Hit@10 for seed 42: .9372, .9331, .9346, .9348), so S0 is pooled over 11 runs (.9361 +/- .0018) as the noise yardstick.

| Variant (factor) | n runs | val Hit@10 mean +/- sd | vs S0 | val-strict Hit@10 (median, min) | forward-time audit Hit@10 (5 seeds) |
|---|---|---|---|---|---|
| S0_base | 11 | .9361 +/- .0018 | - | .9128, .8702 (8 runs) | .5142 +/- .0045 |
| T_gap (log-gap + recency of each item) | 3 | .9362 +/- .0010 | +0.0 | - | .5171 (3 seeds) |
| **C_calendar (month of last event embedding)** | 11 | **.9457 +/- .0012** | **+1.0** | .9205, .9149 (8 runs) | .5192 +/- .0088 (+0.5, n.s.) |
| P_candprior (past-only trending counts + launched/age flags as additive logit prior) | 6 | .9419 +/- .0012 | +0.6 | **.6209, .6198 (collapse in 2 of 3)** | .5295 +/- .0049 (+1.5) |
| Q_trend (trending counts only) | 3 | .9378 +/- .0020 | +0.2 | collapse 1 of 3 | .5293 +/- .0066 (+1.5) |
| Q4_trend_trans (+ recent a->b transition counts) | 3 | .9397 +/- .0013 | +0.4 | **collapse 3 of 3 (.618)** | .5321 +/- .0049 (+1.8) |
| R_recenttrans (transitions only) | 3 | .9370 +/- .0017 | +0.1 | .9140 | not run |
| TCP (gap + calendar + trending prior) | 11 | .9451 +/- .0012 | +0.9 | .9186, .8832 (partial collapse seed 7) | .5346 +/- .0080 (+2.0) |
| TC, CP, TP, TP5 | 3 each | .9444, .9452, .9409, .9412 | +0.5 to +0.9 | TP5 partial collapse | not run |
| AUX02 (aux next-competency/level heads, weight .2) | 3 | .9369 +/- .0025 | +0.1 | - | - |
| LS01 (label smoothing .1) | 3 | .9352 +/- .0025 | -0.1 | - | - |
| AUG03 (crop oldest k items, p=.3) | 3 | .9328 +/- .0003 | -0.3 | - | - |
| 100 epochs, patience 10 (S0 / C_calendar) | 3 | .9365 / .9468 | +0.0 / +1.0 | .9121 / .9080 | - |

Candidate (1) hybrid/ensemble (`x1_ensemble.py`, validation, 5 seeds per family, mean probability):

| Ensemble | Val Hit@10 |
|---|---|
| single SASRec runs / single LSTM-attn runs | .9363-.9385 / .9326-.9348 |
| SASRec x5 / LSTM x5 (seed ensembles) | .9385 / .9402 |
| SASRec x5 + LSTM x5 (mixed, 10 members) | .9413 (+0.1 over best seed ensemble) |
| + fixed Markov prior lam = .02 / .05 / .1 / .2 / .3 | .9404 / .9402 / .9400 / .9389 / .9372 (never above .9413) |
| C_calendar x5 / SAS+LSTM+C_calendar x5 (15 members) | .9489 / .9461 (adding weaker families lowers it) |

Interpretation: mixing architectures adds about 0.1 pt over seed averaging, which is variance reduction, not a new model. A Markov prior never helps.
Candidates not separately implemented: a TiSASRec attention bias (the same gap information as T_gap gave +0.0 at the input, and histories have at most 10 items); competency/level-aware attention (e4 full-features already showed no gain, and an auxiliary loss on the same signals gave +0.1); all-position SASRec loss (the training set already enumerates every prefix, so it is the same supervision).

## 3. Why C_calendar does not count (leakage audit, `x1_timeaudit.py`, validation only)
Protocol limitation: the contract splits per user, so other users' training examples can lie in the calendar future of an evaluated user. A calendar feature can exploit that. Audit: train only on prefixes whose target is before 2025-10-01 (13,870 prefixes), early-stop on validation users before the cut (2,500), evaluate on validation users after it (2,101). The cut was set once from the quarter histogram and not tuned.
Result: all models fall to about 0.51-0.53 Hit@10. C_calendar +0.5 pt (sd .009, noise level); the causal trending priors (past activity only) +1.5 to +2.0 pt (4-5 of 5 seeds), but those priors collapse on the skip-one (strict-like) cohort in 8 of 12 validation-strict runs (P, P5, Q, Q4; 3 seeds each) (Hit@10 .62). Mechanism: course 60/52 has no past activity at the history's last timestamp, so the prior pushes it out of the top-10 for the cohort. This is the same failure that produced the earlier unreproducible seed-89 run.
So: calendar helps only under the leaky-by-construction protocol, trend priors help under forward time but are unstable under strict. Neither is a clean improvement.

## 4. What worked / did not
- Worked (conditionally): C_calendar +1.0 pt val, +0.8 pt val-strict median (.9205 vs .9128), 8/8 val-strict seeds >= baseline (seed 21 baseline partially collapsed), lower strict variance; protocol-dependent.
- Worked only forward-time but unstable: trending / transition priors.
- No effect or worse: gap features, aux heads, label smoothing, cropping augmentation, 100 epochs, Markov prior, LSTM hybrid, all attention variants (earlier E5).
- Not tested on test: nothing here has been run on test except the quick smoke test below.

## 5. Recommendation and honest framing
- Do not present attention, hybridisation, or time-aware machinery as a performance advance. The data support: "sequence models beat Markov and popularity by a wide margin; architecture differences among LSTM, GRU and SASRec are at most 0.4-0.7 pt on non-cohort users; attention adds nothing."
- Defensible novelty is in the evaluation and the data insight:
  1. cohort-structured logs inflate Hit@10 (27 % of users are one curriculum); report all-user and cohort-excluded metrics;
  2. strict (skip-one) protocol discriminates models, default does not;
  3. forward-time audit: Hit@10 about 0.51, which bounds claims about deployment;
  4. instability of rare-course rankings on the cohort across seeds (seed-89 collapse explained).
- If a model result is wanted: "calendar-aware SASRec improves Hit@10 by about 1 pt under the per-user temporal protocol; the gain does not persist under forward-in-time evaluation, so we treat it as era/cohort information rather than improved generalisation." Do not call it an attention or architecture novelty.
- Disclosure of test contact: descriptive cohort split of already-published test results (section 1) and a 2-epoch `x1_final --quick` smoke test (output deleted, not used for any decision).
- Limits: val-strict covers 4,221/4,601 users; audit uses one cut and validation users only; 3-5 seeds per variant in the pilots (11 for S0/C/TCP).

## 6. Files and commands
Created (all in `experiment-2-revision/`): `experiments_new/{xlib,x1_ablation,x1_timeaudit,x1_ensemble,x1_final,x1_analyze}.py`; results `x1_ablation{,2,3,4}_val_seed*.csv`, `x1_long_val_seed*.csv`, `x1_timeaudit_val.csv`, `x1_ensemble_val_summary.csv`, `x1_ensemble_valprobs/`; logs `x1_*.log`.
Run from `/data/Documents/Bu-Ruktin/04-JCMM/CRE_ML_Console_Final_Artifact_Terbaru` (PY=/data/Documents/Bu-Ruktin/03/venv_stitch/bin/python):
```
# 10-seed TEST run of the pre-chosen candidate + paired control (about 20-25 min, resumable, both protocols)
$PY experiment-2-revision/experiments_new/x1_final.py
# cohort split + paired bootstrap CIs (read-only, about 1 min); second call compares with the published e4 SASRec
$PY experiment-2-revision/experiments_new/x1_analyze.py --tag x1_final
$PY experiment-2-revision/experiments_new/x1_analyze.py --tag x1_final --control sasrec_e4
# optional exploratory (expect strict instability): add the trend-prior variant
$PY experiment-2-revision/experiments_new/x1_final.py --variants S0_base C_calendar TCP
```
Smoke tests passed (`--quick` of x1_ablation, x1_final, x1_analyze, x1_timeaudit, x1_ensemble); quick outputs were deleted. Pass criterion for the test run: C_calendar must beat S0_base on BOTH protocols with a paired CI excluding 0 and no seed collapse; otherwise report it as a negative result.
