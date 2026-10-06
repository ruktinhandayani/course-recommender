"""x1_timeaudit - LEAKAGE AUDIT of the time-aware features, on the VALIDATION set only.
The published protocol splits per user (last course = test, second last = validation), so training examples of OTHER users can lie
in the calendar future of an evaluated user.  A calendar/time feature could in principle exploit that.  This audit enforces a GLOBAL
time split: train only on prefixes whose target happened before T_CUT, early-stop on validation users whose target is before T_CUT,
and evaluate on validation users whose target is at/after T_CUT (strictly the future of everything the model saw).
Model inputs never include the target timestamp; the audit only uses it to define the split.
Run: python experiment-2-revision/experiments_new/x1_timeaudit.py [--cut 2025-10-01] [--seeds 42 101 202] [--variants S0_base TCP ...]"""
import argparse, os, sys, warnings, json
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2"); os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202])
ap.add_argument("--variants", nargs="+", default=["S0_base", "T_gap", "C_calendar", "P_candprior", "TCP"])
ap.add_argument("--cut", default="2025-10-01")
ap.add_argument("--tag", default="x1_timeaudit_val")
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
from common.provenance import start_run, say, ROOT
TAG = "x1quick_timeaudit" if args.quick else args.tag
log, meta = start_run(TAG, args)
import numpy as np, pandas as pd, keras, xlib
from common.metrics import evaluate_scores
from common.data_pipeline import build_dataset
from common.contract import assert_contract
D = build_dataset(); assert_contract(D, raw=True)
FE = xlib.attach(D, xlib.build_features(D))
cut = (pd.Timestamp(args.cut) - xlib.T0).total_seconds() / 86400
tr, va = FE["train"], FE["val"]
m_tr, m_va_early, m_va_eval = tr["t_target"] < cut, va["t_target"] < cut, va["t_target"] >= cut
say(f"global cut {args.cut}: train prefixes {m_tr.sum()}/{len(m_tr)}, early-stop val users {m_va_early.sum()}, FUTURE eval val users {m_va_eval.sum()}")
def sub(F, m):
    G = {k: (v[m] if isinstance(v, np.ndarray) and len(v) == len(m) else v) for k, v in F.items()}
    G["aux"] = (F["aux"][0][m], F["aux"][1][m]); return G
FEa = {"train": sub(tr, m_tr), "val": sub(va, m_va_early), "future": sub(va, m_va_eval)}
rows, f = [], ROOT / "results" / f"{TAG}.csv"
if f.exists(): rows = pd.read_csv(f).to_dict("records")
done = {(r["variant"], r["seed"]) for r in rows}
seen_f = D.seen_val[m_va_eval]
for seed in ([42] if args.quick else args.seeds):
    for nm in args.variants:
        if (nm, seed) in done: say(f"{nm} seed {seed}: done"); continue
        cfg = dict(xlib.VARIANTS[nm]); cfg.pop("augment_p", None)
        keras.utils.set_random_seed(seed); m = xlib.build_model(D, cfg)
        mon = "val_loss"
        h = m.fit(xlib.inputs_of(FEa["train"]), FEa["train"]["_y"], validation_data=(xlib.inputs_of(FEa["val"]), FEa["val"]["_y"]),
                  epochs=2 if args.quick else 50, batch_size=64, shuffle=True, verbose=0,
                  callbacks=[keras.callbacks.EarlyStopping(monitor=mon, patience=5, restore_best_weights=True),
                             keras.callbacks.ReduceLROnPlateau(monitor=mon, mode="min", factor=0.5, patience=2, min_lr=1e-5)])
        p = m.predict(xlib.inputs_of(FEa["future"]), batch_size=512, verbose=0)
        r, _, _ = evaluate_scores(p, seen_f, FEa["future"]["_y"], D.num_courses)
        rows.append({"variant": nm, "seed": seed, "cut": args.cut, "n_train": int(m_tr.sum()), "n_future_eval": int(m_va_eval.sum()),
                     "epochs": len(h.history["loss"]), **{f"future_{k}": float(v) for k, v in r.items()}})
        pd.DataFrame(rows).to_csv(f, index=False)
        say(f"{nm} seed {seed}: FUTURE-eval Hit@10={r['Hit@10']:.4f} Hit@1={r['Hit@1']:.4f} MRR@10={r['MRR@10']:.4f} epochs={len(h.history['loss'])}")
        keras.backend.clear_session()
df = pd.DataFrame(rows); say("SUMMARY (mean/sd over seeds, future-eval on validation users)")
print(df.groupby("variant")[["future_Hit@10", "future_Hit@1", "future_MRR@10"]].agg(["mean", "std"]).round(4).to_string())
say(f"{TAG} DONE")
