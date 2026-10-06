"""e3b - GRU4Rec-style + the paper's TemporalAttention (representation = [final GRU state ; attention context]), with and without the side features (course_only / full_features = the LSTM's five inputs).
Hyperparameters are tuned on the VALIDATION target (seed 42), then the chosen configuration is trained for every seed and
evaluated once on the test set, default + strict protocol, full-history masking.  Resumable (re-run to continue).
Run:  python experiment-2-revision/experiments/e3b_gru4rec_ta.py             (full: tuning + 10 seeds x 2 settings)
      python experiment-2-revision/experiments/e3b_gru4rec_ta.py --quick     (smoke test: 3 epochs, 1 config, 1 seed; writes e3bquick_* files)
Options: --seeds 42 101 ...  --epochs 50  --batch-size 64  --patience 5  --tune-seed 42  --retune
         --tag NAME   write results under another name (e.g. a 100-epoch run: --epochs 100 --tag e3blong)
         --wide       larger tuning grid"""
import argparse, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.provenance import start_run, say, save_json, ROOT
ap = argparse.ArgumentParser()
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202, 7, 13, 21, 34, 55, 89, 144])
ap.add_argument("--epochs", type=int, default=50)
ap.add_argument("--batch-size", type=int, default=64)
ap.add_argument("--patience", type=int, default=5)
ap.add_argument("--tune-seed", type=int, default=42)
ap.add_argument("--tag", default="e3b", help="name prefix of the result files")
ap.add_argument("--wide", action="store_true", help="larger tuning grid")
ap.add_argument("--retune", action="store_true", help="ignore a saved tuning file and tune again")
ap.add_argument("--quick", action="store_true", help="smoke test only")
args = ap.parse_args()
TAG = args.tag + "quick" if args.quick else args.tag
if args.quick:
    args.epochs, args.seeds = 3, [42]
log, meta = start_run(f"{TAG}_gru4rec_ta", args)
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.models import build_gru4rec_ta
from common.runner import run_experiment
GRID = {"units": [64, 128, 192, 256], "dropout": [0.2, 0.3, 0.4]} if args.wide else {"units": [64, 128, 192], "dropout": [0.2, 0.3]}
say("STEP 1  dataset + contract")
D = build_dataset()
assert_contract(D, raw=True)
best = run_experiment("gru4rec_ta", TAG, build_gru4rec_ta, GRID, D, args)
save_json({"meta": meta, "grid": GRID, "chosen": best}, ROOT / "results" / f"{TAG}_meta.json")
say(f"{TAG} DONE")
