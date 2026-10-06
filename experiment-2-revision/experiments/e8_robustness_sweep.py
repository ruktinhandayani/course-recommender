"""E8 - robustness sweep for the two preprocessing thresholds the reviewers asked about (comment 8):
MIN_COURSE_COUNT_TRAIN (vocabulary-inclusion threshold, published value 20) and the minimum per-user history
length used to admit a user into the temporal split (published value 4).

For each threshold value, the FULL pipeline is rebuilt from raw data (different vocabulary, different users,
different train/val/test sizes) -- this is not a model-only ablation. Popularity, first-order Markov, and the
primary LSTM+attention model (3 seeds: 42, 101, 202, matching the existing repeated-run convention in
Supplementary Table S4) are evaluated on both protocols at every threshold. Only the canonical point
(count=20, history=4) is checked against assert_contract(); every other point is deliberately off-contract by
design, and is logged as such rather than silently compared.

Cost: ~5 course-count values + ~5 history values (canonical point shared) x 3 LSTM seeds x ~1 min/seed + two
near-instant baselines per point -> well under an hour on the GPU box.

Run:   python experiment-2-revision/experiments/e8_robustness_sweep.py
Watch: tail -f experiment-2-revision/logs/e8_robustness_*.log
Resumable: a (sweep, value, seed) cell already present in results/e8_robustness.csv is skipped.
"""
import argparse, os, sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--seeds", type=int, nargs="+", default=[42, 101, 202])
ap.add_argument("--course-counts", type=int, nargs="+", default=[10, 15, 20, 30, 40])
ap.add_argument("--min-history", type=int, nargs="+", default=[2, 3, 4, 6, 8])
ap.add_argument("--quick", action="store_true", help="smoke test: seed 42 only, tag e8quick, deletes itself")
args = ap.parse_args()
TAG = "e8quick" if args.quick else "e8_robustness"
if args.quick:
    args.seeds = [42]
from common.provenance import start_run, say, save_json, ROOT, order_digest
log, meta = start_run(TAG, args)

import numpy as np, pandas as pd, keras
import common.data_pipeline as dp
from common.data_pipeline import build_dataset, MIN_COURSE_COUNT_TRAIN as CANON_COUNT, MIN_USER_HISTORY_FOR_SPLIT as CANON_HIST
from common.contract import assert_contract
from common.metrics import evaluate_scores
from common.baselines import popularity, transition_counts, score_markov
from common.models import build_lstm_attention

say("STEP 0  canonical sanity check (count=20, history=4) -- must match the published contract before the sweep is trusted")
D0 = build_dataset(min_course_count=CANON_COUNT)
assert_contract(D0, raw=True)
say(f"  canonical OK: courses={D0.num_courses-1} train_rows={len(D0.train_enc)} test={len(D0.y_test)}")

out = ROOT / "results"
csv = out / f"{TAG}.csv"
rows = pd.read_csv(csv).to_dict("records") if csv.exists() else []
done = {(r["sweep"], r["value"], r["model"], r["seed"], r["protocol"]) for r in rows}


def run_point(sweep, value, D):
    """Build is done by the caller; this runs Popularity+Markov+LSTM(seeds) on dataset D and appends to `rows`."""
    say(f"  [{sweep}={value}] courses={D.num_courses-1} comps={D.num_competencies-1} levels={D.num_levels-1} "
        f"train_users={D.train_enc['user_id'].nunique()} train_rows={len(D.train_enc)} "
        f"val={len(D.y_val)} test_default={len(D.y_test)} test_strict={len(D.y_test_strict)}")
    pop = popularity(D); C1, _, _ = transition_counts(D)
    for nm, (X, y, mt) in D.splits.items():
        for model_name, scores in (("popularity", np.tile(pop, (len(y), 1))), ("markov_1st", score_markov(D, X, C1, pop)[0])):
            key = (sweep, value, model_name, -1, nm)
            if key in done:
                continue
            r, _, _ = evaluate_scores(scores, D.seen[nm], y, D.num_courses)
            rows.append({"sweep": sweep, "value": value, "model": model_name, "seed": -1, "protocol": nm,
                         "n_courses": D.num_courses - 1, "n_train_users": D.train_enc["user_id"].nunique(),
                         "n_train_rows": len(D.train_enc), "n_test": len(y), **{k: float(v) for k, v in r.items()}})
            say(f"    {model_name:11s} {nm:8s} " + "  ".join(f"{k}={float(v):.4f}" for k, v in r.items()))
    for seed in args.seeds:
        if all((sweep, value, "lstm_attn", seed, nm) in done for nm in D.splits):
            say(f"  [{sweep}={value}] seed {seed}: already done, skipping"); continue
        say(f"  [{sweep}={value}] seed {seed}: training LSTM+attention")
        keras.utils.set_random_seed(seed)
        m = build_lstm_attention(D, seed=seed)
        t0 = time.time()
        m.fit(D.X_train, D.y_train, validation_data=(D.X_val, D.y_val), epochs=50, batch_size=64, shuffle=True, verbose=0,
              callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", mode="min", patience=5, restore_best_weights=True),
                         keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)])
        say(f"    trained in {time.time()-t0:.0f}s")
        for nm, (X, y, mt) in D.splits.items():
            key = (sweep, value, "lstm_attn", seed, nm)
            if key in done:
                continue
            r, _, _ = evaluate_scores(m.predict(X, batch_size=512, verbose=0), D.seen[nm], y, D.num_courses)
            rows.append({"sweep": sweep, "value": value, "model": "lstm_attn", "seed": seed, "protocol": nm,
                         "n_courses": D.num_courses - 1, "n_train_users": D.train_enc["user_id"].nunique(),
                         "n_train_rows": len(D.train_enc), "n_test": len(y), **{k: float(v) for k, v in r.items()}})
            say(f"    lstm_attn   {nm:8s} " + "  ".join(f"{k}={float(v):.4f}" for k, v in r.items()))
        keras.backend.clear_session()
        pd.DataFrame(rows).to_csv(csv, index=False)


say("STEP 1  sweep MIN_COURSE_COUNT_TRAIN (history fixed at canonical 4)")
for v in sorted(set(args.course_counts) | {CANON_COUNT}):
    D = D0 if v == CANON_COUNT else build_dataset(min_course_count=v)
    run_point("min_course_count_train", v, D)

say("STEP 2  sweep minimum per-user history length (vocabulary threshold fixed at canonical 20)")
for v in sorted(set(args.min_history) | {CANON_HIST}):
    if v == CANON_HIST:
        run_point("min_user_history", v, D0)
        continue
    dp.MIN_USER_HISTORY_FOR_SPLIT = v
    try:
        D = build_dataset(min_course_count=CANON_COUNT)
    finally:
        dp.MIN_USER_HISTORY_FOR_SPLIT = CANON_HIST  # always restore, even on error
    run_point("min_user_history", v, D)

df = pd.DataFrame(rows)
df.to_csv(csv, index=False)
agg = df[df.seed != -1].groupby(["sweep", "value", "model", "protocol"])[["Hit@10", "MRR@10"]].agg(["mean", "std"]).round(4)
say("SUMMARY (LSTM, mean/std over seeds) + deterministic baselines are in the saved csv")
print(agg.to_string())
save_json({"meta": meta, "seeds": args.seeds, "course_counts": sorted(set(args.course_counts) | {CANON_COUNT}),
           "min_history": sorted(set(args.min_history) | {CANON_HIST})}, out / f"{TAG}_meta.json")
say(f"{TAG} DONE -> {csv}")
if args.quick:
    csv.unlink(missing_ok=True)
    say("quick smoke test: output file removed (not a reported result)")
