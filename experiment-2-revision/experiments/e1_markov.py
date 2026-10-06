"""E1 - First-order Markov baseline (course only) + popularity reference. CPU only, about 20 s.
Counts transitions (last course -> next course) in the TRAIN CORE only; users whose last course has no observed
transition fall back to course popularity. Same full-history masking and metrics as the LSTM, both protocols.
Run:  python experiment-2-revision/experiments/e1_markov.py"""
import argparse, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.provenance import start_run, say, save_json, ROOT, user_codes, order_digest
ap = argparse.ArgumentParser()
ap.add_argument("--protocol", choices=["default", "strict", "both"], default="both",
                help="evaluation setting(s): default (history incl. validation target), strict (train history only), or both")
args = ap.parse_args()
log, meta = start_run("e1_markov", args)

import numpy as np, pandas as pd
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.metrics import evaluate_scores
from common.baselines import popularity, transition_counts, score_markov

say("STEP 1/3  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)
say("STEP 2/3  train-core transition counts")
pop = popularity(D); C1, _, _ = transition_counts(D)
say(f"  observed transitions: {int(C1.sum())}; distinct (a->b) pairs: {int((C1 > 0).sum())}")

say("STEP 3/3  evaluation")
rows, arrays = [], {}
for nm, (X, y, mt) in D.splits.items():
    if args.protocol != "both" and nm != args.protocol:
        continue
    S, seen = score_markov(D, X, C1, pop)
    say(f"  [{nm}] users whose last course has observed transitions: {seen.mean()*100:.1f}%  (rest fall back to popularity)")
    for model, scores in (("popularity", np.tile(pop, (len(y), 1))), ("markov_1st", S)):
        r, pu, top = evaluate_scores(scores, D.seen[nm], y, D.num_courses)
        rows.append({"model": model, "protocol": nm, "n": len(y), **{k: float(v) for k, v in r.items()}})
        for k, v in pu.items(): arrays[f"{model}_{nm}_{k}"] = v
        arrays[f"{model}_{nm}_top10"] = top
        say(f"  {model:11s} {nm:8s} " + "  ".join(f"{k}={float(v):.4f}" for k, v in r.items()))
    arrays[f"{nm}_y"] = y; arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
    c = user_codes(mt["user_id"])
    if c: arrays[f"{nm}_user_code"] = np.array(c)
out = ROOT / "results"
pd.DataFrame(rows).to_csv(out / "e1_markov.csv", index=False); say(f"wrote {out/'e1_markov.csv'}")
np.savez_compressed(out / "e1_markov_peruser.npz", **arrays)
save_json({"meta": meta, "rows": rows}, out / "e1_markov.json")
say("E1 DONE")
