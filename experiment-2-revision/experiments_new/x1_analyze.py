"""x1_analyze - read-only analysis of finished test runs (results/x1_final_peruser/*.npz plus the earlier e4/e5 per-user files).
For every model and protocol: Hit@10 / Hit@1 / MRR@10 on all users, on the single mass cohort (users whose train-core history is exactly
46->47->21; ~27% of the test set, target almost always course 60) and on the non-cohort users, plus paired bootstrap 95% CIs
(10,000 resamples over test users, seed-averaged per-user outcomes) of the difference to the control.  Does not train anything.
Run: python experiment-2-revision/experiments_new/x1_analyze.py [--tag x1_final] [--control sasrec_e4]"""
import argparse, glob, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser(); ap.add_argument("--tag", default="x1_final"); ap.add_argument("--control", default="S0_base"); ap.add_argument("--boot", type=int, default=10000)
args = ap.parse_args()
from common.provenance import start_run, say, ROOT, order_digest
log, meta = start_run(f"{args.tag}_analyze", args)
import numpy as np, pandas as pd
from common.data_pipeline import build_dataset
D = build_dataset()
sx = {u: tuple(s[s != 0]) for u, s in zip(D.meta_test_strict.user_id.values, D.X_test_strict[0])}
metas = {"default": D.meta_test, "strict": D.meta_test_strict}
coh = {pr: np.array([sx.get(u) == (46, 47, 21) for u in m.user_id.values]) for pr, m in metas.items()}
R = ROOT / "results"
SRC = {"sasrec_e4": "e4_peruser/sasrec_course_only_seed*.npz", "lstm_attn_e5": "e5_peruser/A_custom_attention_seed*.npz",
       "lstm_noattn_e5": "e5_peruser/B_no_attention_seed*.npz"}
for f in sorted(glob.glob(str(R / f"{args.tag}_peruser/*_seed*.npz"))):
    nm = Path(f).name.split("_seed")[0]; SRC.setdefault(nm, f"{args.tag}_peruser/{nm}_seed*.npz")
data = {}
for nm, pat in SRC.items():
    fs = sorted(glob.glob(str(R / pat)))
    if not fs: continue
    zs = [np.load(f) for f in fs]
    for pr in ("default", "strict"):
        assert all(str(z[f"{pr}_order_sha256"]) == order_digest(metas[pr].user_id) for z in zs), f"user order mismatch {nm}"
    data[nm] = {pr: {k: np.mean([z[f"{pr}_{k}"] for z in zs], 0) for k in ("hit1", "hit10", "rr10")} for pr in ("default", "strict")}
    data[nm]["n"] = len(zs)
rows = []
for nm, d in data.items():
    for pr in ("default", "strict"):
        c = coh[pr]
        rows.append({"model": nm, "protocol": pr, "n_seeds": d["n"], "Hit@10_all": d[pr]["hit10"].mean(), "Hit@10_cohort": d[pr]["hit10"][c].mean(),
                     "Hit@10_noncohort": d[pr]["hit10"][~c].mean(), "Hit@1_noncohort": d[pr]["hit1"][~c].mean(), "MRR@10_noncohort": d[pr]["rr10"][~c].mean()})
tab = pd.DataFrame(rows); say("per-model metrics (seed-averaged per-user outcomes)"); print(tab.round(4).to_string(index=False))
tab.to_csv(R / f"{args.tag}_cohort_split.csv", index=False)
rng = np.random.default_rng(0); out = []
ctrl = args.control if args.control in data else "sasrec_e4"
for nm in data:
    if nm == ctrl: continue
    for pr in ("default", "strict"):
        for sub, m in (("all", np.ones(len(coh[pr]), bool)), ("noncohort", ~coh[pr])):
            diff = (data[nm][pr]["hit10"] - data[ctrl][pr]["hit10"])[m]; n = len(diff)
            bs = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(args.boot)])
            out.append({"model": nm, "control": ctrl, "protocol": pr, "users": sub, "diff_Hit@10": diff.mean(), "ci_lo": np.percentile(bs, 2.5), "ci_hi": np.percentile(bs, 97.5)})
res = pd.DataFrame(out); say(f"paired bootstrap, difference to control '{ctrl}' (positive = better than control)"); print(res.round(4).to_string(index=False))
res.to_csv(R / f"{args.tag}_paired_bootstrap_vs_{ctrl}.csv", index=False); say("DONE")
