# Data contract for the JCMM revision experiments

Established and verified on 2026-10-03. If any statement here is unclear, the code in `common/` is the authority and
`experiments/e0a_verify_data.py` proves it. **Every experiment script calls `assert_contract()` first and stops on mismatch.**

## Which data
- Raw folder: `CRE_ML_Console_Final_Artifact_Terbaru/data/` (default; relative `DATA_DIR` is always resolved from the
  project root, never from the current directory). It is the data behind the submitted paper.
- Fingerprints (md5): interactions `132de42fc9526715d335b4eb3b246500`, users `df26d20a3a07e17b165533648cc526eb`,
  courses `3ad82e313e81214e6ae89105a311f4a2`, course_alias_map `098ca854270cfa9a22d512fad49904b8`.
- `learning_progress_*.csv` in `data/` are NOT used by the experiments.
- Anonymized data (`data_anonymized/`) is used only for the final GitHub check (Phase 6): counts must equal this contract;
  the md5 and user-set checks are skipped (`raw=False`).

## Pipeline rules (these reproduce the published run exactly)
1. Read every CSV as text (`dtype=str`): leading zeros in `user_id` (e.g. `000123451`) must survive.
2. Clean names/IDs, map legacy course ids through `course_alias_map.csv`, remove 15 noise/test courses (3,412 interactions).
3. **Drop user-course pairs that consist only of the 291 legacy `certified` rows** (no enrollment, no timestamp).
   Certified rows next to an enrollment are kept (9 rows). Implemented as `enrolled_available_raw == 1`.
4. Keep users with at least 4 courses; temporal split per user: last course = test target, second last = validation
   target, everything before = train core. Course vocabulary = courses with >= 20 train-core interactions (60 courses).
5. Encoders and the certificate scaler are fitted on train core only. Sequence length 10, pre-padding.
6. **Masking = `full_pre_target_history`**: every course the user has ever taken before the target is excluded from
   the ranking (not only the last 10 shown to the model). Use `D.seen[...]`, never the padded input, as the mask.
7. Two evaluation settings, always both: **default** (history = everything before the test target, includes the
   validation target) and **strict** (history = train core only).

## Expected numbers (any deviation = stop)
| item | value |
|---|---|
| courses / competencies / levels (incl. unknown) | 60 / 27 / 5 |
| train core rows / users | 35,346 / 4,803 |
| training sequences | 30,543 |
| validation / test (default) / test (strict) | 4,601 / 4,553 / 4,551 |
| certificate scaler max | 2 |
| saved model, default | Hit@1 0.5998, Hit@5 0.8386, Hit@10 0.9273, MRR@10 0.7011, NDCG@10 0.7552 |
| saved model, strict | Hit@1 0.1206, Hit@5 0.7704, Hit@10 0.8842, MRR@10 0.4177, NDCG@10 0.5330 |
| popularity baseline, default | Hit@10 about 0.407 (0.4072 here vs 0.4068 published: tie-breaking only) |

## Things that were ambiguous before (now settled)
- The notebook in `notebooks/research/` is an OLDER version than the published artifacts: it lacks rules 1, 3 and 6.
  Do not use it for numbers. It also crashes on pandas 3.
- With the old notebook on the same data you would get 61 courses, 4,501 test users and Hit@10 0.9128 for the saved
  model; that is the wrong pipeline, not a data problem.

## Result files
- Written to `results/`; per-user `.npz` files hold hit vectors, top-10 lists, an order digest and (only if
  `CRE_ML_ANON_SALT` is set) pseudonym codes `U-xxxxxxxxxx`. Raw user IDs are never written.
- Every log in `logs/` starts with versions, GPU, data path and file md5s.
