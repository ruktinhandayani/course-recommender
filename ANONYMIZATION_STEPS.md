# Anonymization + GitHub publication — manual steps

Run these yourself, in order, on the Linux machine. Nothing here touches
`data/` or `course_recommender_artifacts_final/` in place — everything
anonymized lands in new `*_anonymized/` folders, and the raw folders stay
local only.

## Two phases — do Phase A now, Phase B later

**Phase A (do this now): Steps 0–3.** Salt, build the pseudonym mapping,
apply it, verify. This is entirely local — it never touches git, and
nothing leaves this machine. Run these now and stop.

**Phase B (defer until every reviewer-requested experiment is finished):
Steps 4–6.** Creating the repo, tagging, and pushing to GitHub. Don't run
any command in these steps yet. When `experiment-2-revision/` (the new
baselines, multi-seed CIs, etc.) is complete, come back to this file and
pick up at Step 4 — the pseudonym mapping and `data_anonymized/` /
`course_recommender_artifacts_final_anonymized/` from Phase A will still
be valid and reusable, as long as you kept the same salt.

---

## PHASE A — run now

## 0. One-time setup

```bash
cd "CRE_ML_Console_Final_Artifact_Terbaru"
python3 -V            # 3.9+ is fine, stdlib only, no pip installs needed
git init               # if this repo isn't already a git repo
```

Generate a secret salt **once** and store it somewhere safe outside the
repo (password manager, or a local file outside this folder). Do not skip
this — if you lose it, you can't re-verify old pseudonym codes later, and
if you regenerate it, everyone's code changes.

```bash
openssl rand -hex 32
```

Export it into your shell for this session (re-export every time you open
a new terminal to re-run these scripts):

```bash
export CRE_ML_ANON_SALT="paste-the-hex-string-here"
```

## 1. Build the pseudonym mapping

```bash
python3 scripts/anonymize/generate_pseudonyms.py
```

This reads `data/*.csv` and the user-level artifact tables, and writes
`data_private/user_id_mapping.csv` (original `user_id` → `U-xxxxxxxxxx`
code). This mapping file is the only place the link exists — it is already
covered by `.gitignore`, but double-check with:

```bash
git check-ignore -v data_private/user_id_mapping.csv
```

If that prints nothing, **stop** — the `.gitignore` isn't being picked up,
and you must fix that before continuing.

## 2. Apply the mapping

```bash
python3 scripts/anonymize/apply_pseudonyms.py
```

Produces:
- `data_anonymized/` — same CSVs as `data/`, but `user_id` pseudonymized
  and `full_name` removed from `users.csv`.
- `course_recommender_artifacts_final_anonymized/` — same tree as
  `course_recommender_artifacts_final/`, with `user_id` pseudonymized in
  the six tables that carry it, everything else (model weights, scalers,
  encoder mappings, configs, non-user tables) copied through unchanged.

Read the console output — it flags any row with an *unmapped* `user_id`,
which would mean a new ID showed up after you built the mapping in step 1.
If you see that, re-run step 1 before continuing.

## 3. Verify before you push anything

```bash
python3 scripts/anonymize/verify_anonymization.py
```

This must print `RESULT: all checks passed.` If it reports any `[FAIL]`
lines, fix the underlying issue and re-run steps 2–3 — do not proceed to
git until this is clean. It checks for: leftover `full_name` columns, any
raw original `user_id` surviving anywhere (including inside the `.keras`
model file and `.pkl` files, scanned as raw bytes), row-count mismatches,
and email- or NIK-shaped strings anywhere in the output.

**Phase A is done here.** `data_anonymized/` and
`course_recommender_artifacts_final_anonymized/` now exist and are
verified clean. You do not need to do anything else until
`experiment-2-revision/` (all reviewer-requested baselines and multi-seed
evaluation) is complete. No git repo, no GitHub account, no push — none of
that is needed yet.

When you come back for Phase B, re-run Step 3 once more first (quick,
confirms nothing changed), then continue below.

---

## PHASE B — defer until all reviewer experiments are done

## 4. What goes to GitHub vs. what stays local

| Keep local only (never push) | Push to GitHub |
|---|---|
| `data/` | `data_anonymized/` |
| `data_private/user_id_mapping.csv` | `course_recommender_artifacts_final_anonymized/` |
| `.env` (real secrets) | `.env.example` (placeholders only, already present) |
| the salt itself | everything else: code, docs, Dockerfile |

`course_recommender_artifacts_final/` (the non-anonymized original) should
also stay local — the `.gitignore` already blocks its six user-bearing
tables specifically; if you'd rather not think about which six, simplest
is to just not `git add course_recommender_artifacts_final/` at all and
only add the `_anonymized` copy.

## 5. Two-tagged-experiment GitHub workflow

Per the plan: push the original submitted pipeline first, then do the
reviewer-driven revision work as a second, clearly separated experiment.

```bash
# --- experiment 1: what was originally submitted ---
git add .gitignore README.md course_recommender/ docs/ Dockerfile \
        docker-compose.yml .env.example .env.production.example \
        data_anonymized/ course_recommender_artifacts_final_anonymized/ \
        scripts/anonymize/ ANONYMIZATION_STEPS.md
git status   # READ THIS OUTPUT — confirm no raw data/, no data_private/, no .env
git commit -m "Experiment 1: original submitted pipeline (anonymized data)"
git tag v1-submitted

git remote add origin <your-new-github-repo-url>
git push -u origin main
git push origin v1-submitted
```

Then, once the new baselines (GRU4Rec, SASRec, competency-aware Markov,
multi-seed CIs, etc.) are implemented in a separate folder as planned
(e.g. `experiment-2-revision/`):

```bash
git checkout -b revision
git add experiment-2-revision/
git status   # same check as above, every time
git commit -m "Experiment 2: reviewer-requested additional baselines and multi-seed evaluation"
git tag v2-revision
git push -u origin revision
git push origin v2-revision
```

Keep `v1-submitted` and `v2-revision` as separate tags/branches so the
response letter can point reviewers at exactly what ran for the original
submission vs. what's new.

## 6. Before every future push, re-run the verifier

Any time you regenerate `data_anonymized/` or
`course_recommender_artifacts_final_anonymized/` (e.g. after adding a new
baseline that touches user-level tables), re-run step 3 before `git add`.
Treat a failing verifier as a hard stop, not a warning.
