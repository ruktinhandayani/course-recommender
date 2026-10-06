"""E7 statistics - paired bootstrap CIs for the budget-matched (Optuna-tuned) models, and for the effect of tuning itself. Read-only, CPU, ~20 s.
Same method as e6_paired_ci.py: per-user outcomes averaged over the 10 seeds, 10,000 paired bootstrap resamples of test users, 95% percentile CI, two-sided
bootstrap p, Holm within each (variant, protocol, subset, metric) family; subsets all / non-cohort; variants all seeds / without seed 89; seed-level view.
Inputs : results/e7_peruser (tuned models), results/e5/e3/e3b/e4/e4b_peruser (the earlier, lightly tuned models)
Outputs: results/<tag>stats_models.csv, _paired_ci.csv, _seed_level.csv, _meta.json  (tag e7 -> e7stats_*, e7b -> e7bstats_*)
Run    : python experiment-2-revision/experiments/e7_paired_ci.py [--boot 10000] [--skip-contract]
Positive diff = first-named model better."""
import argparse, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=10000); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--skip-contract", action="store_true")
ap.add_argument("--tuned-tag", default="e7", help="e7 (objective: validation Hit@10) or e7b (objective: mean of default and strict validation Hit@10); output prefix <tag>stats")
args = ap.parse_args()
from common.provenance import start_run, say, ROOT, order_digest, save_json
PFX = f"{args.tuned_tag}stats"
log, meta = start_run(PFX, args)
import numpy as np, pandas as pd
from common.data_pipeline import build_dataset
D = build_dataset()
if not args.skip_contract:
    from common.contract import assert_contract; assert_contract(D)
metas = {"default": D.meta_test, "strict": D.meta_test_strict}
digest = {pr: order_digest(m.user_id) for pr, m in metas.items()}
sx = {u: tuple(s[s != 0]) for u, s in zip(D.meta_test_strict.user_id.values, D.X_test_strict[0])}
cohort = {pr: np.array([sx.get(u) == (46, 47, 21) for u in m.user_id.values]) for pr, m in metas.items()}
R = ROOT / "results"; SEEDS = [42, 101, 202, 7, 13, 21, 34, 55, 89, 144]; METRICS = ["hit10", "rr10", "hit1"]
T = lambda n: f"{args.tuned_tag}_peruser/{n}_tuned_seed{{s}}.npz"
SEEDED = {"LSTM no attn (tuned)": T("lstm_noattn"), "LSTM+attn (tuned)": T("lstm_attn"), "LSTM+Keras MHA (tuned)": T("lstm_mha"),
          "GRU4Rec (tuned)": T("gru4rec"), "GRU4Rec+TA (tuned)": T("gru4rec_ta"), "SASRec (tuned)": T("sasrec"), "SASRec+TA (tuned)": T("sasrec_ta"),
          "LSTM no attn (E5)": "e5_peruser/B_no_attention_seed{s}.npz", "LSTM+attn (E5)": "e5_peruser/A_custom_attention_seed{s}.npz", "LSTM+Keras MHA (E5)": "e5_peruser/C_keras_mha_seed{s}.npz",
          "GRU4Rec (E3)": "e3_peruser/gru4rec_course_only_seed{s}.npz", "GRU4Rec+TA (E3b)": "e3b_peruser/gru4rec_ta_course_only_seed{s}.npz",
          "SASRec (E4)": "e4_peruser/sasrec_course_only_seed{s}.npz", "SASRec+TA (E4b)": "e4b_peruser/sasrec_ta_course_only_seed{s}.npz"}
if args.tuned_tag != "e7":      # also load E7 so that the effect of the selection objective can be tested
    for k, n in (("LSTM no attn", "lstm_noattn"), ("LSTM+attn", "lstm_attn"), ("LSTM+Keras MHA", "lstm_mha"), ("GRU4Rec", "gru4rec"), ("GRU4Rec+TA", "gru4rec_ta"), ("SASRec", "sasrec"), ("SASRec+TA", "sasrec_ta")):
        SEEDED[f"{k} (E7)"] = f"e7_peruser/{n}_tuned_seed{{s}}.npz"
SEEDED = {k: v for k, v in SEEDED.items() if (R / v.format(s=42)).exists()}      # a tuned model that was not run (e.g. lstm_mha in E7b) is skipped
per = {}
say("loading per-user files and verifying user order")
for nm, pat in SEEDED.items():
    per[nm] = {pr: {m: {} for m in METRICS} for pr in metas}
    for s in SEEDS:
        z = np.load(R / pat.format(s=s))
        for pr in metas:
            assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {nm} {s} {pr}"
            for m in METRICS: per[nm][pr][m][s] = z[f"{pr}_{m}"]
    say(f"  {nm:26s} seeds={len(per[nm]['default']['hit10'])}")
FIXED = {"Markov 1st": ("e1_markov_peruser.npz", "markov_1st"), "Popularity": ("e1_markov_peruser.npz", "popularity")}      # deterministic references
for nm, (fn, key) in FIXED.items():
    z = np.load(R / fn); per[nm] = {pr: {m: {None: z[f"{key}_{pr}_{m}"]} for m in METRICS} for pr in metas}
    for pr in metas: assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {nm}"
avg = lambda nm, pr, m, ex=(): np.mean([v for k, v in per[nm][pr][m].items() if k not in ex], 0)
# sanity: tuned means equal the summary printed by E7
sm = pd.read_csv(R / f"{args.tuned_tag}.csv")
for nm, key in (("SASRec (tuned)", "sasrec_tuned"), ("LSTM+attn (tuned)", "lstm_attn_tuned")):
    for pr in metas:
        assert abs(avg(nm, pr, "hit10").mean() - sm[(sm.model == key) & (sm.protocol == pr)]["Hit@10"].mean()) < 1e-9
say("  sanity: tuned Hit@10 equals e7.csv")

rows = []
for nm in per:
    for pr in metas:
        c = cohort[pr]; r = {"model": nm, "protocol": pr}
        for m in METRICS: v = avg(nm, pr, m); r[f"{m}_all"] = v.mean(); r[f"{m}_noncohort"] = v[~c].mean()
        ks = [v.mean() for v in per[nm][pr]["hit10"].values()]; r["hit10_seed_sd"] = np.std(ks, ddof=1) if len(ks) > 1 else np.nan; r["hit10_seed_min"] = min(ks); rows.append(r)
pd.DataFrame(rows).to_csv(R / f"{PFX}_models.csv", index=False)

COMPS = [  # (a, b, group)
    ("LSTM+attn (tuned)", "LSTM no attn (tuned)", "attention effect"), ("LSTM+attn (tuned)", "LSTM+Keras MHA (tuned)", "attention effect"),
    ("GRU4Rec+TA (tuned)", "GRU4Rec (tuned)", "attention effect"), ("SASRec+TA (tuned)", "SASRec (tuned)", "attention effect"),
    ("SASRec (tuned)", "LSTM no attn (tuned)", "backbone, no TA"), ("GRU4Rec (tuned)", "LSTM no attn (tuned)", "backbone, no TA"), ("SASRec (tuned)", "GRU4Rec (tuned)", "backbone, no TA"),
    ("SASRec+TA (tuned)", "LSTM+attn (tuned)", "backbone, with TA"), ("GRU4Rec+TA (tuned)", "LSTM+attn (tuned)", "backbone, with TA"), ("SASRec+TA (tuned)", "GRU4Rec+TA (tuned)", "backbone, with TA"),
    ("LSTM no attn (tuned)", "LSTM no attn (E5)", "tuning effect"), ("LSTM+attn (tuned)", "LSTM+attn (E5)", "tuning effect"), ("LSTM+Keras MHA (tuned)", "LSTM+Keras MHA (E5)", "tuning effect"),
    ("GRU4Rec (tuned)", "GRU4Rec (E3)", "tuning effect"), ("GRU4Rec+TA (tuned)", "GRU4Rec+TA (E3b)", "tuning effect"),
    ("SASRec (tuned)", "SASRec (E4)", "tuning effect"), ("SASRec+TA (tuned)", "SASRec+TA (E4b)", "tuning effect")]
if args.tuned_tag != "e7":
    COMPS += [(f"{k} (tuned)", f"{k} (E7)", "objective effect (vs E7)") for k in ("LSTM no attn", "LSTM+attn", "LSTM+Keras MHA", "GRU4Rec", "GRU4Rec+TA", "SASRec", "SASRec+TA")]
COMPS += [("LSTM+attn (tuned)", "Markov 1st", "reference baselines"), ("SASRec (tuned)", "Markov 1st", "reference baselines"), ("LSTM+attn (tuned)", "Popularity", "reference baselines")]
COMPS = [c for c in COMPS if c[0] in per and c[1] in per]
rng = np.random.default_rng(args.seed)
def boot_means(Dm, B):
    n = Dm.shape[0]; out = np.empty((B, Dm.shape[1])); i = 0
    while i < B:
        b = min(500, B - i); idx = rng.integers(0, n, (b, n)); W = np.zeros((b, n), np.float32)
        for r in range(b): W[r] = np.bincount(idx[r], minlength=n)
        out[i:i + b] = (W @ Dm.astype(np.float32)) / n; i += b
    return out
def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for rank, j in enumerate(o): run = max(run, (m - rank) * p[j]); adj[j] = min(1.0, run)
    return adj
say(f"paired bootstrap: {len(COMPS)} comparisons x 2 protocols x 2 subsets x {len(METRICS)} metrics x 2 variants")
res = []
for vname, ex in {"mean_all_seeds": (), "mean_excl_seed89": (89,)}.items():
    for pr in metas:
        for sub in ("all", "noncohort"):
            keep = np.ones(len(cohort[pr]), bool) if sub == "all" else ~cohort[pr]; cols, lab = [], []
            for a, b, g in COMPS:
                for m in METRICS: cols.append((avg(a, pr, m, ex) - avg(b, pr, m, ex))[keep]); lab.append((a, b, g, m))
            Dm = np.stack(cols, 1); bm = boot_means(Dm, args.boot); pt = Dm.mean(0)
            lo, hi = np.percentile(bm, 2.5, 0), np.percentile(bm, 97.5, 0); p = np.maximum(2 * np.minimum((bm <= 0).mean(0), (bm >= 0).mean(0)), 1.0 / args.boot)
            for (a, b, g, m), d, l, h, pv in zip(lab, pt, lo, hi, p):
                res.append({"variant": vname, "protocol": pr, "subset": sub, "metric": m, "group": g, "a": a, "b": b, "n_users": int(keep.sum()), "diff": d, "ci_lo": l, "ci_hi": h,
                            "p_boot": pv, "ci_excludes_0": bool(l > 0 or h < 0)})
res = pd.DataFrame(res); res["p_holm"] = np.nan
for _, idx in res.groupby(["variant", "protocol", "subset", "metric"]).groups.items(): res.loc[idx, "p_holm"] = holm(res.loc[idx, "p_boot"].values)
res["significant_holm_05"] = res["p_holm"] < 0.05; res.to_csv(R / f"{PFX}_paired_ci.csv", index=False)
sl = []
for a, b, g in COMPS:
    if a in FIXED or b in FIXED: continue
    for pr in metas:
        d = np.array([per[a][pr]["hit10"][s].mean() - per[b][pr]["hit10"][s].mean() for s in SEEDS])
        sl.append({"a": a, "b": b, "group": g, "protocol": pr, "mean_diff": d.mean(), "median_diff": np.median(d), "sd_diff": d.std(ddof=1), "seeds_a_better": int((d > 0).sum()),
                   "mean_diff_excl89": np.mean([x for x, s in zip(d, SEEDS) if s != 89])})
pd.DataFrame(sl).to_csv(R / f"{PFX}_seed_level.csv", index=False)
for met in ("hit10", "rr10"):
    say(f"HEADLINE {met}, all users, all seeds (* CI excludes 0, H Holm-significant)")
    h = res[(res.variant == "mean_all_seeds") & (res.metric == met) & (res.subset == "all")]
    for pr in metas:
        print(f"--- {pr}")
        for _, r in h[h.protocol == pr].iterrows():
            print(f"  {'*' if r.ci_excludes_0 else ' '}{'H' if r.significant_holm_05 else ' '} [{r.group:17s}] {r.a:24s} - {r.b:24s} {r['diff']:+.4f} [{r.ci_lo:+.4f},{r.ci_hi:+.4f}] p_holm={r.p_holm:.4f}")
save_json({"boot": args.boot, "comparisons": len(COMPS), "models": list(per)}, R / f"{PFX}_meta.json"); say(f"{PFX} DONE")
