"""E6 - paired confidence intervals and significance tests (reviewer-requested statistics). Read-only: trains nothing, needs no GPU.

Inputs  : per-user npz files written by E1-E5 (results/*_peruser).  Each file's user order is checked against the data contract.
Method  : per-user outcomes are averaged over the 10 seeds (so one number per test user and model), then
          * paired bootstrap, 10,000 resamples of test users, 95% percentile CI of the mean difference (a - b; positive = a better);
            subsets: all users and non-cohort users (the 27% who follow the fixed 46->47->21 curriculum are removed);
          * two-sided bootstrap p-value, Holm-corrected within each (metric, protocol, subset, variant) family;
          * sensitivity: the same bootstrap with seed 89 excluded, and seed-level paired differences (median over seeds, seeds won);
          * exact McNemar test on Hit@10 for seed 42 (single-run view, as most papers report it).
Outputs : results/e6_models.csv, e6_paired_ci.csv, e6_seed_level.csv, e6_mcnemar.csv, e6_meta.json, logs/e6_*.log
Run     : python experiment-2-revision/experiments/e6_paired_ci.py [--boot 10000] [--skip-contract] [--quick]
Positive diff = the first-named model is better.  A CI that contains 0 means the difference is not distinguishable from noise."""
import argparse, glob, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--boot", type=int, default=10000)
ap.add_argument("--seed", type=int, default=0, help="bootstrap RNG seed")
ap.add_argument("--skip-contract", action="store_true")
ap.add_argument("--quick", action="store_true", help="smoke test: 200 resamples, tag e6quick")
args = ap.parse_args()
TAG = "e6quick" if args.quick else "e6"
if args.quick: args.boot = 200
from common.provenance import start_run, say, ROOT, order_digest, save_json
log, meta = start_run(TAG, args)
import numpy as np, pandas as pd
from scipy.stats import binomtest
from common.data_pipeline import build_dataset

say("STEP 1  dataset + contract (only to check user order and to define the cohort)")
D = build_dataset()
if not args.skip_contract:
    from common.contract import assert_contract
    assert_contract(D)
metas = {"default": D.meta_test, "strict": D.meta_test_strict}
digest = {pr: order_digest(m.user_id) for pr, m in metas.items()}
sx = {u: tuple(s[s != 0]) for u, s in zip(D.meta_test_strict.user_id.values, D.X_test_strict[0])}
cohort = {pr: np.array([sx.get(u) == (46, 47, 21) for u in m.user_id.values]) for pr, m in metas.items()}
for pr in cohort: say(f"  {pr}: {len(cohort[pr])} users, cohort (46->47->21) {cohort[pr].sum()} = {cohort[pr].mean():.1%}")

R = ROOT / "results"
SEEDS = [42, 101, 202, 7, 13, 21, 34, 55, 89, 144]
METRICS = ["hit10", "rr10", "hit1"]
# name -> (glob pattern relative to results/, seeded?)   Markov/popularity are deterministic: one array, key prefix given instead
SEEDED = {
    "LSTM+attn (A, paper)": "e5_peruser/A_custom_attention_seed{s}.npz",
    "LSTM no attn (B)": "e5_peruser/B_no_attention_seed{s}.npz",
    "LSTM+Keras MHA (C)": "e5_peruser/C_keras_mha_seed{s}.npz",
    "GRU4Rec": "e3_peruser/gru4rec_course_only_seed{s}.npz",
    "GRU4Rec+feat": "e3_peruser/gru4rec_full_features_seed{s}.npz",
    "GRU4Rec+TA": "e3b_peruser/gru4rec_ta_course_only_seed{s}.npz",
    "SASRec": "e4_peruser/sasrec_course_only_seed{s}.npz",
    "SASRec+feat": "e4_peruser/sasrec_full_features_seed{s}.npz",
    "SASRec+TA": "e4b_peruser/sasrec_ta_course_only_seed{s}.npz",
}
if (R / "e4long_peruser").is_dir():
    SEEDED["SASRec 100ep"] = "e4long_peruser/sasrec_course_only_seed{s}.npz"
FIXED = {"Popularity": ("e1_markov_peruser.npz", "popularity"), "Markov 1st": ("e1_markov_peruser.npz", "markov_1st"),
         "Markov+ctx 2nd": ("e2_markov_ctx_peruser.npz", "markov_ctx_2nd")}

say("STEP 2  loading per-user files and verifying user order")
per = {}      # model -> protocol -> metric -> {seed: array}  (fixed models use seed key None)
for nm, pat in SEEDED.items():
    per[nm] = {pr: {m: {} for m in METRICS} for pr in metas}
    for s in SEEDS:
        f = R / pat.format(s=s)
        if not f.exists():
            if nm == "SASRec 100ep": continue
            raise SystemExit(f"FAIL missing {f}")
        z = np.load(f)
        for pr in metas:
            assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {f.name} {pr}"
            for m in METRICS: per[nm][pr][m][s] = z[f"{pr}_{m}"]
    got = sorted(per[nm]["default"]["hit10"]); say(f"  {nm:24s} seeds={len(got)}")
for nm, (fn, key) in FIXED.items():
    z = np.load(R / fn); per[nm] = {pr: {m: {None: z[f"{key}_{pr}_{m}"]} for m in METRICS} for pr in metas}
    for pr in metas: assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {fn}"
    say(f"  {nm:24s} deterministic")


def avg(nm, pr, m, exclude=()):
    d = per[nm][pr][m]; ks = [k for k in d if k not in exclude]
    return np.mean([d[k] for k in ks], 0)


# ---- published sanity check -------------------------------------------------------------------------------------------------------
PUB = {("SASRec", "default"): 0.9282, ("SASRec", "strict"): 0.8909, ("LSTM+attn (A, paper)", "default"): 0.9235, ("LSTM+attn (A, paper)", "strict"): 0.8821,
       ("Markov 1st", "default"): 0.8669, ("Markov 1st", "strict"): 0.5511}
for (nm, pr), v in PUB.items():
    got = avg(nm, pr, "hit10").mean(); assert abs(got - v) < 6e-4, f"{nm} {pr}: {got:.4f} != recorded {v}"
say("  sanity: SASRec, LSTM+attn, Markov Hit@10 match the values recorded in E1-E5")

# ---- model table -------------------------------------------------------------------------------------------------------------------
rows = []
for nm in per:
    for pr in metas:
        c = cohort[pr]
        r = {"model": nm, "protocol": pr, "n_seeds": len(per[nm][pr]["hit10"])}
        for m in METRICS:
            v = avg(nm, pr, m); r[f"{m}_all"] = v.mean(); r[f"{m}_noncohort"] = v[~c].mean()
        r["hit10_cohort"] = avg(nm, pr, "hit10")[c].mean()
        ks = list(per[nm][pr]["hit10"])
        r["hit10_seed_sd"] = np.std([per[nm][pr]["hit10"][k].mean() for k in ks], ddof=1) if len(ks) > 1 else np.nan
        r["hit10_seed_min"] = min(per[nm][pr]["hit10"][k].mean() for k in ks)
        rows.append(r)
mt = pd.DataFrame(rows); mt.to_csv(R / f"{TAG}_models.csv", index=False)
say("per-model table (test; seed-averaged per-user outcomes)")
print(mt[["model", "protocol", "n_seeds", "hit10_all", "hit10_noncohort", "hit10_seed_sd", "hit10_seed_min", "rr10_all"]].round(4).to_string(index=False))

# ---- comparisons -------------------------------------------------------------------------------------------------------------------
L = "LSTM+attn (A, paper)"
COMPS = [  # (a, b, group)   diff = a - b
    ("SASRec", L, "backbone"), ("GRU4Rec", L, "backbone"),
    ("SASRec", "GRU4Rec", "backbone"),
    (L, "LSTM no attn (B)", "attention"), (L, "LSTM+Keras MHA (C)", "attention"),
    ("GRU4Rec+TA", "GRU4Rec", "attention"), ("SASRec+TA", "SASRec", "attention"),
    ("SASRec+feat", "SASRec", "features"), ("GRU4Rec+feat", "GRU4Rec", "features"),
    (L, "Markov 1st", "baseline"), ("SASRec", "Markov 1st", "baseline"), (L, "Popularity", "baseline"), ("Markov+ctx 2nd", "Markov 1st", "baseline"),
]
if "SASRec 100ep" in per: COMPS.append(("SASRec 100ep", "SASRec", "training length"))
VARIANTS = {"mean_all_seeds": (), "mean_excl_seed89": (89,)}
rng = np.random.default_rng(args.seed)


def boot_means(D_, B):
    """D_: n x K matrix of per-user differences. Returns B x K bootstrap means (resampling users) using count-weights and one matmul per chunk."""
    n = D_.shape[0]; out = np.empty((B, D_.shape[1]), np.float64); i = 0
    while i < B:
        b = min(500, B - i); idx = rng.integers(0, n, (b, n))
        W = np.zeros((b, n), np.float32)
        for r in range(b): W[r] = np.bincount(idx[r], minlength=n)
        out[i:i + b] = (W @ D_.astype(np.float32)) / n; i += b
    return out


def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for rank, j in enumerate(o):
        run = max(run, (m - rank) * p[j]); adj[j] = min(1.0, run)
    return adj


say(f"STEP 3  paired bootstrap ({args.boot} resamples) for {len(COMPS)} comparisons x 2 protocols x 2 subsets x {len(METRICS)} metrics x {len(VARIANTS)} variants")
res = []
for vname, excl in VARIANTS.items():
    for pr in metas:
        for sub in ("all", "noncohort"):
            keep = np.ones(len(cohort[pr]), bool) if sub == "all" else ~cohort[pr]
            cols, labels = [], []
            for a, b, g in COMPS:
                for m in METRICS:
                    cols.append((avg(a, pr, m, excl) - avg(b, pr, m, excl))[keep]); labels.append((a, b, g, m))
            Dm = np.stack(cols, 1); bm = boot_means(Dm, args.boot); pt = Dm.mean(0)
            lo, hi = np.percentile(bm, 2.5, 0), np.percentile(bm, 97.5, 0)
            p = 2 * np.minimum((bm <= 0).mean(0), (bm >= 0).mean(0)); p = np.maximum(p, 1.0 / args.boot)
            for (a, b, g, m), d, l, h, pv in zip(labels, pt, lo, hi, p):
                res.append({"variant": vname, "protocol": pr, "subset": sub, "metric": m, "group": g, "a": a, "b": b, "n_users": int(keep.sum()),
                            "diff": d, "ci_lo": l, "ci_hi": h, "p_boot": pv, "ci_excludes_0": bool(l > 0 or h < 0)})
res = pd.DataFrame(res)
res["p_holm"] = np.nan
for _, idx in res.groupby(["variant", "protocol", "subset", "metric"]).groups.items():
    res.loc[idx, "p_holm"] = holm(res.loc[idx, "p_boot"].values)
res["significant_holm_05"] = res["p_holm"] < 0.05
res.to_csv(R / f"{TAG}_paired_ci.csv", index=False)

say("HEADLINE  Hit@10, seed-averaged, all seeds (positive = first model better; * = CI excludes 0; H = also significant after Holm)")
h = res[(res.variant == "mean_all_seeds") & (res.metric == "hit10")]
for pr in metas:
    for sub in ("all", "noncohort"):
        print(f"\n--- {pr} / {sub} users ---")
        for _, r in h[(h.protocol == pr) & (h.subset == sub)].iterrows():
            flag = ("*" if r.ci_excludes_0 else " ") + ("H" if r.significant_holm_05 else " ")
            print(f"  {flag} {r.a:22s} - {r.b:22s} {r['diff']:+.4f}  [{r.ci_lo:+.4f}, {r.ci_hi:+.4f}]  p_holm={r.p_holm:.4f}")

# ---- seed-level view ---------------------------------------------------------------------------------------------------------------
say("STEP 4  seed-level paired differences (same seed, both models) and exact McNemar on seed 42")
sl, mc = [], []
for a, b, g in COMPS:
    for pr in metas:
        sa, sb = per[a][pr]["hit10"], per[b][pr]["hit10"]
        common = [s for s in SEEDS if s in sa and s in sb]
        if common:
            d = np.array([sa[s].mean() - sb[s].mean() for s in common])
            sl.append({"a": a, "b": b, "group": g, "protocol": pr, "n_seeds": len(common), "mean_diff": d.mean(), "median_diff": np.median(d), "sd_diff": d.std(ddof=1),
                       "min_diff": d.min(), "max_diff": d.max(), "seeds_a_better": int((d > 0).sum()),
                       "mean_diff_excl89": np.mean([x for x, s in zip(d, common) if s != 89])})
        s0 = 42 if (42 in sa and 42 in sb) else (None if (None in sa and None in sb) else "x")
        if s0 == "x": continue
        xa, xb = sa[s0], sb[s0]; n10 = int(((xa == 1) & (xb == 0)).sum()); n01 = int(((xa == 0) & (xb == 1)).sum())
        p = binomtest(n10, n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
        mc.append({"a": a, "b": b, "group": g, "protocol": pr, "seed": s0 if s0 is not None else "deterministic", "a_only_correct": n10, "b_only_correct": n01, "p_mcnemar_exact": p})
sl = pd.DataFrame(sl); mc = pd.DataFrame(mc)
mc["p_holm"] = np.nan
for pr, idx in mc.groupby("protocol").groups.items(): mc.loc[idx, "p_holm"] = holm(mc.loc[idx, "p_mcnemar_exact"].values)
sl.to_csv(R / f"{TAG}_seed_level.csv", index=False); mc.to_csv(R / f"{TAG}_mcnemar.csv", index=False)
print(sl.round(4).to_string(index=False)); print(mc.round(4).to_string(index=False))

# ---- automatic read-out ------------------------------------------------------------------------------------------------------------
say("STEP 5  read-out (all 10 seeds, Hit@10, all users)")
def get(a, b, pr, sub="all", v="mean_all_seeds", m="hit10"):
    r = res[(res.a == a) & (res.b == b) & (res.protocol == pr) & (res.subset == sub) & (res.variant == v) & (res.metric == m)].iloc[0]; return r
for a, b, text in [("SASRec", L, "SASRec better than the paper's LSTM"), (L, "LSTM no attn (B)", "attention helps the LSTM"),
                   ("SASRec+TA", "SASRec", "temporal attention helps SASRec"), ("GRU4Rec+TA", "GRU4Rec", "temporal attention helps GRU4Rec")]:
    out = []
    for pr in metas:
        r = get(a, b, pr); out.append(f"{pr} {r['diff']:+.4f} [{r.ci_lo:+.4f},{r.ci_hi:+.4f}] " + ("YES" if r.ci_lo > 0 else "reversed" if r.ci_hi < 0 else "no (CI contains 0)"))
    print(f"  {text}: " + " | ".join(out))
r89 = res[(res.variant == "mean_excl_seed89") & (res.metric == "hit10")].merge(
    res[(res.variant == "mean_all_seeds") & (res.metric == "hit10")], on=["protocol", "subset", "a", "b"], suffixes=("_x89", "_all"))
flip = r89[r89.ci_excludes_0_x89 != r89.ci_excludes_0_all]
say(f"  excluding seed 89 changes the CI-excludes-0 verdict in {len(flip)} of {len(r89)} comparisons" + ("" if flip.empty else ":"))
if not flip.empty: print(flip[["protocol", "subset", "a", "b", "diff_all", "diff_x89"]].round(4).to_string(index=False))
save_json({"boot": args.boot, "bootstrap_seed": args.seed, "comparisons": len(COMPS), "models": list(per), "cohort_rule": "train-core history == (46,47,21)",
           "cohort_share": {pr: float(cohort[pr].mean()) for pr in cohort}}, R / f"{TAG}_meta.json")
say(f"{TAG} DONE  -> results/{TAG}_*.csv")
