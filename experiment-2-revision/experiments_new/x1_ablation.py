"""x1_ablation - VALIDATION-ONLY (val = default-like, vstrict = skip-one analogue of the strict protocol, both on VALIDATION targets) ablation of the time-aware SASRec ('X-SASRec') factors and generic tricks.
Every row = one training run evaluated on the VALIDATION target (test is never touched here).
Run:  python experiment-2-revision/experiments_new/x1_ablation.py --seeds 42 --variants S0_base TCP ...
      python experiment-2-revision/experiments_new/x1_ablation.py --quick     (smoke test, writes x1quick_* only, deleted by you)
Resumable: rows already in results/x1_ablation_val_seed<S>.csv are skipped."""
import argparse, os, sys, warnings, json
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2"); os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202])
ap.add_argument("--variants", nargs="+", default=None)
ap.add_argument("--epochs", type=int, default=50)
ap.add_argument("--patience", type=int, default=5)
ap.add_argument("--tag", default="x1_ablation_val")
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
from common.provenance import start_run, say, ROOT
TAG = "x1quick_ablation_val" if args.quick else args.tag
if args.quick:
    args.epochs, args.seeds = 2, [42]
log, meta = start_run(TAG, args)
import pandas as pd, xlib
from common.data_pipeline import build_dataset
from common.contract import assert_contract
say("STEP 1  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)
FE = xlib.attach(D, xlib.build_features(D)); say("features built and alignment asserted (course/timestamp padding, targets)")
names = args.variants or list(xlib.VARIANTS)
if args.quick:
    names = ["S0_base", "TCP", "AUX02", "LS01", "AUG03"]
for seed in args.seeds:
    f = ROOT / "results" / f"{TAG}_seed{seed}.csv"
    rows = pd.read_csv(f).to_dict("records") if f.exists() else []
    done = {r["variant"] for r in rows}
    for nm in names:
        if nm in done:
            say(f"[seed {seed}] {nm}: done, skipping"); continue
        cfg = dict(xlib.VARIANTS[nm]); aug = cfg.pop("augment_p", 0.0)
        say(f"[seed {seed}] {nm}: {xlib.VARIANTS[nm]}")
        r = xlib.train_eval(D, FE, cfg, seed, epochs=args.epochs, patience=args.patience, splits=("val", "vstrict"), augment=aug)
        rows.append({"variant": nm, "seed": seed, "cfg": json.dumps(xlib.VARIANTS[nm]), **{f"val_{k}": v for k, v in r["val"].items()}, **{f"vstrict_{k}": v for k, v in r["vstrict"].items()},
                     "best_val_loss": r["best_val_loss"], "epochs": r["epochs"], "params": r["params"], "sec": round(r["sec"])})
        pd.DataFrame(rows).to_csv(f, index=False)
        say(f"    val Hit@10={r['val']['Hit@10']:.4f} Hit@1={r['val']['Hit@1']:.4f} MRR@10={r['val']['MRR@10']:.4f} | val-strict Hit@10={r['vstrict']['Hit@10']:.4f} | loss={r['best_val_loss']:.4f} epochs={r['epochs']} ({r['sec']:.0f}s)")
say(f"{TAG} DONE")
