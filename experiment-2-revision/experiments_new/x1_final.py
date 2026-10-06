"""x1_final - FINAL TEST RUN of PRE-CHOSEN configurations (chosen on VALIDATION, see results/IMPROVEMENT_REPORT_ml_engineer.md).
For every variant x seed: train (same recipe as e4: Adam 1e-3, batch 64, <=50 epochs, EarlyStopping(val_loss, patience 5), LR halving),
evaluate on TEST with BOTH protocols (default + strict, full-history masking) and store per-user arrays in the same format as e4_peruser
(so a paired bootstrap / E6 can read them).  The test set is evaluated exactly once per (variant, seed); nothing is selected from it.
Resumable.  Variants are defined in xlib.VARIANTS; S0_base is the plain SASRec re-run through the same code path (paired control).
Run:   python experiment-2-revision/experiments_new/x1_final.py                       (default variants, 10 seeds; ~1 min per run)
       python experiment-2-revision/experiments_new/x1_final.py --quick               (smoke test: 2 epochs, 1 seed; writes x1quick_* only)
Options: --variants S0_base P_candprior ...   --seeds 42 101 ...   --tag x1_final"""
import argparse, os, sys, warnings, json, time
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2"); os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202, 7, 13, 21, 34, 55, 89, 144])
ap.add_argument("--variants", nargs="+", default=["S0_base", "C_calendar"])   # pre-chosen on validation (see report); add TCP for the exploratory trend-prior variant
ap.add_argument("--tag", default="x1_final")
ap.add_argument("--epochs", type=int, default=50)
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
from common.provenance import start_run, say, save_json, ROOT, order_digest
TAG = "x1quick_final" if args.quick else args.tag
if args.quick:
    args.epochs, args.seeds = 2, [42]
log, meta = start_run(TAG, args)
import numpy as np, pandas as pd, xlib
from common.data_pipeline import build_dataset
from common.contract import assert_contract
say("STEP 1  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)
FE = xlib.attach(D, xlib.build_features(D)); say("features built; alignment with D.X_* asserted")
pdir = ROOT / "results" / f"{TAG}_peruser"; pdir.mkdir(exist_ok=True)
csv = ROOT / "results" / f"{TAG}.csv"; rows = pd.read_csv(csv).to_dict("records") if csv.exists() else []
runs = [(v, s) for s in args.seeds for v in args.variants]; t0, ran = time.time(), 0
say(f"STEP 2  {len(runs)} runs: variants {args.variants} x seeds {args.seeds}  (test evaluated once per run)")
for k, (nm, seed) in enumerate(runs, 1):
    f = pdir / f"{nm}_seed{seed}.npz"
    if f.exists():
        say(f"[{k}/{len(runs)}] {nm} seed {seed}: already done, skipping"); continue
    cfg = dict(xlib.VARIANTS[nm]); aug = cfg.pop("augment_p", 0.0)
    say(f"[{k}/{len(runs)}] {nm} seed {seed}: {xlib.VARIANTS[nm]}")
    r = xlib.train_eval(D, FE, cfg, seed, epochs=args.epochs, splits=("val", "default", "strict"), augment=aug)
    arrays = {}
    for pr in ("default", "strict"):
        rows.append({"model": nm, "seed": seed, "protocol": pr, "cfg": json.dumps(xlib.VARIANTS[nm]), "params": r["params"], "epochs_run": r["epochs"],
                     "best_val_loss": r["best_val_loss"], "val_Hit@10": r["val"]["Hit@10"], **r[pr]})
        for kk, vv in r[pr + "_peruser"].items():
            arrays[f"{pr}_{kk}"] = vv
        arrays[f"{pr}_top10"], arrays[f"{pr}_y"] = r[pr + "_top10"], FE[pr]["_y"]
        arrays[f"{pr}_order_sha256"] = np.array(order_digest((D.meta_test if pr == "default" else D.meta_test_strict)["user_id"]))
        say(f"    {pr:8s} " + "  ".join(f"{kk}={vv:.4f}" for kk, vv in r[pr].items() if kk != "Coverage@10"))
    np.savez_compressed(f, **arrays); pd.DataFrame(rows).to_csv(csv, index=False)
    ran += 1; el = time.time() - t0; say(f"    saved {f.name}; elapsed {el/60:.1f} min, estimated remaining {(len(runs)-k)*el/ran/60:.1f} min")
df = pd.read_csv(csv); mc = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10", "Coverage@10"]
agg = df.groupby(["model", "protocol"])[mc].agg(["mean", "std"]).round(4); agg["n_seeds"] = df.groupby(["model", "protocol"]).size()
agg.to_csv(ROOT / "results" / f"{TAG}_summary.csv"); say("SUMMARY (test, mean / std over seeds)"); print(agg.to_string())
# paired comparison against the control, per seed (same seed, same code path)
ctrl = "S0_base"
if ctrl in set(df.model):
    for nm in sorted(set(df.model) - {ctrl}):
        for pr in ("default", "strict"):
            a = df[(df.model == nm) & (df.protocol == pr)].set_index("seed")["Hit@10"]; b = df[(df.model == ctrl) & (df.protocol == pr)].set_index("seed")["Hit@10"]
            d = (a - b).dropna(); say(f"PAIRED {nm} - {ctrl} [{pr}] Hit@10: mean diff {d.mean():+.4f} (sd {d.std():.4f}, n={len(d)}, seeds with gain {int((d>0).sum())}/{len(d)})")
save_json({"meta": meta, "variants": {v: xlib.VARIANTS[v] for v in args.variants}}, ROOT / "results" / f"{TAG}_meta.json"); say(f"{TAG} DONE")
