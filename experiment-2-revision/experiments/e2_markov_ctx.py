"""E2 - Markov with competency + level (fair comparison for an LSTM that sees competency and level). CPU only.
Models: markov_ctx      = (1-lam) P(next|last course) + lam P(next|competency,level of last course)
        markov_ctx_2nd  = markov_ctx plus a second-order term P(next | last two courses), weight mu where observed
lam in {0,.25,.5,.75,1} and mu in {.25,.5,.75,1} are chosen on the VALIDATION target only (Hit@10, ties by MRR@10);
the test set is evaluated once with the chosen values.
Run:  python experiment-2-revision/experiments/e2_markov_ctx.py"""
import argparse, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.provenance import start_run, say, save_json, ROOT, user_codes, order_digest
ap = argparse.ArgumentParser()
ap.add_argument("--protocol", choices=["default", "strict", "both"], default="both",
                help="evaluation setting(s): default (history incl. validation target), strict (train history only), or both")
args = ap.parse_args()
log, meta = start_run("e2_markov_ctx", args)

import numpy as np, pandas as pd
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.metrics import evaluate_scores
from common.baselines import popularity, transition_counts, score_markov_ctx, score_markov_ctx_2nd

say("STEP 1/4  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)
say("STEP 2/4  train-core counts"); pop = popularity(D); C1, Cctx, C2 = transition_counts(D)

say("STEP 3/4  tuning on validation (test untouched)")
Xv, yv = D.X_val, D.y_val
def val_score(scores):
    r, _, _ = evaluate_scores(scores, D.seen_val, yv, D.num_courses); return r["Hit@10"], r["MRR@10"]
grid1 = []
for lam in (0, .25, .5, .75, 1):
    s, _ = score_markov_ctx(D, Xv, C1, Cctx, pop, lam); h, m = val_score(s); grid1.append((h, m, lam))
    say(f"  ctx   lam={lam:<4} val Hit@10={h:.4f} MRR@10={m:.4f}")
_, _, lam_best = max(grid1)
grid2 = []
for mu in (.25, .5, .75, 1):
    s, _ = score_markov_ctx_2nd(D, Xv, C1, Cctx, C2, pop, lam_best, mu); h, m = val_score(s); grid2.append((h, m, mu))
    say(f"  2nd   mu={mu:<5} (lam={lam_best}) val Hit@10={h:.4f} MRR@10={m:.4f}")
_, _, mu_best = max(grid2)
say(f"  chosen: lam={lam_best}, mu={mu_best}")

say("STEP 4/4  test evaluation, both protocols")
rows, arrays = [], {}
for nm, (X, y, mt) in D.splits.items():
    if args.protocol != "both" and nm != args.protocol:
        continue
    models = {"markov_ctx": score_markov_ctx(D, X, C1, Cctx, pop, lam_best)[0],
              "markov_ctx_2nd": score_markov_ctx_2nd(D, X, C1, Cctx, C2, pop, lam_best, mu_best)[0]}
    for model, scores in models.items():
        r, pu, top = evaluate_scores(scores, D.seen[nm], y, D.num_courses)
        rows.append({"model": model, "protocol": nm, "n": len(y), "lam": lam_best, "mu": mu_best if "2nd" in model else np.nan,
                     **{k: float(v) for k, v in r.items()}})
        for k, v in pu.items(): arrays[f"{model}_{nm}_{k}"] = v
        arrays[f"{model}_{nm}_top10"] = top
        say(f"  {model:15s} {nm:8s} " + "  ".join(f"{k}={float(v):.4f}" for k, v in r.items()))
    arrays[f"{nm}_y"] = y; arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
    c = user_codes(mt["user_id"])
    if c: arrays[f"{nm}_user_code"] = np.array(c)
out = ROOT / "results"
pd.DataFrame(rows).to_csv(out / "e2_markov_ctx.csv", index=False); say(f"wrote {out/'e2_markov_ctx.csv'}")
np.savez_compressed(out / "e2_markov_ctx_peruser.npz", **arrays)
save_json({"meta": meta, "rows": rows, "val_grid_ctx": grid1, "val_grid_2nd": grid2, "lam": lam_best, "mu": mu_best}, out / "e2_markov_ctx.json")
say("E2 DONE")
