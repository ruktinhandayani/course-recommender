"""E0a - DATA GATE (about 1-2 min). Rebuilds the dataset and proves it is exactly the data/split behind the paper:
  1. raw file fingerprints (md5), 2. every published count, vocabulary, encoder, scaler, 3. same validation/test users,
  4. the SAVED published model (no training) reproduces the published metrics on this pipeline.
Run from anywhere:  python experiment-2-revision/experiments/e0a_verify_data.py
Exit code 0 = PASS, 2 = FAIL (do not run anything else)."""
import argparse, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.provenance import start_run, say, save_json, ROOT, ARTIFACTS
ap = argparse.ArgumentParser(); args = ap.parse_args()
log, meta = start_run("e0a_verify_data", args)

import numpy as np, keras, pandas as pd
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.models import TemporalAttention
from common.metrics import evaluate_scores

say("STEP 1/3  building dataset (cleaning, noise filter, temporal split, encoders)")
D = build_dataset()
say("STEP 2/3  contract check against published artifacts")
assert_contract(D, raw=True)

say("STEP 3/3  evaluating the SAVED published model (no training) on this pipeline")
model = keras.models.load_model(ARTIFACTS / "model/cre-lstm-attention-h2-seed42-fullmask-v1.keras",
                                custom_objects={"TemporalAttention": TemporalAttention}, compile=False)
PUB = {"default": {"Hit@1": 0.5998242916758182, "Hit@5": 0.8385679771579179, "Hit@10": 0.9273006808697563,
                   "MRR@10": 0.7010925118271922, "NDCG@10": 0.7551951726244, "Coverage@10": 1.0},
       "strict": {"Hit@1": 0.12063282794990111, "Hit@5": 0.7703801362337948, "Hit@10": 0.8842012744451769,
                  "MRR@10": 0.41768336280531404, "NDCG@10": 0.5330031595828997}}
ok, out = True, {}
for nm, (X, y, _) in D.splits.items():
    r, _, _ = evaluate_scores(model.predict(X, batch_size=512, verbose=0), D.seen[nm], y, D.num_courses)
    out[nm] = {k: float(v) for k, v in r.items()}
    for k, pub in PUB[nm].items():
        good = abs(r[k] - pub) < 5e-4
        ok &= good
        say(f"  [{'PASS' if good else 'FAIL'}] {nm:8s} {k:12s} mine={r[k]:.6f} published={pub:.6f} diff={r[k]-pub:+.6f}")
save_json({"meta": meta, "metrics": out, "pass": bool(ok)}, ROOT / "results/e0a_data_check.json")
if not ok:
    say("E0a FAILED - the pipeline does not reproduce the published model's metrics."); raise SystemExit(2)
say("E0a PASSED - data, split, encoders and evaluation are an exact match to the published run.")
