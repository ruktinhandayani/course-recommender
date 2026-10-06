"""P4a - build results_master.csv (single source of truth for every number in the manuscript) and cross-check it against the recorded runs.

Read-only on E0-E6 outputs; CPU only; trains nothing.  Every number is RECOMPUTED from the per-user npz files (results/*_peruser) and then
compared with what each experiment recorded in its own csv at full precision.  Any mismatch stops the script, so figures and tables can
never drift away from the data.

Outputs (results/):
  results_master.csv      one row per model x protocol x subset x metric: mean / sd / min / max over seeds, n_seeds, params, source
  p4_per_seed.csv         one row per model x seed x protocol x subset (all metrics)  -> seed-level plots
  p4_hitk_curves.csv      Hit@k for k = 1..10 per model x protocol (seed mean, seed min, seed max)
  p4_attention_diag.csv   per-seed attention diagnostics for the three attention models
  p4_attention_by_len.csv the same by history length (2..10)
  p4_crosscheck.csv       recomputed vs recorded, max absolute difference per source file
  p4_meta.json            counts (users per protocol / subset), cohort rule, data md5
Run: python experiment-2-revision/experiments/p4_build_master.py [--skip-contract]
"""
import argparse, json, os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser(); ap.add_argument("--skip-contract", action="store_true"); args = ap.parse_args()
from common.provenance import start_run, say, ROOT, order_digest
log, meta = start_run("p4_build_master", args)
import numpy as np, pandas as pd
from common.data_pipeline import build_dataset

say("STEP 1  dataset + contract (user order digests and cohort definition only)")
D = build_dataset()
if not args.skip_contract:
    from common.contract import assert_contract
    assert_contract(D)
metas = {"default": D.meta_test, "strict": D.meta_test_strict}
digest = {pr: order_digest(m.user_id) for pr, m in metas.items()}
sx = {u: tuple(s[s != 0]) for u, s in zip(D.meta_test_strict.user_id.values, D.X_test_strict[0])}
cohort = {pr: np.array([sx.get(u) == (46, 47, 21) for u in m.user_id.values]) for pr, m in metas.items()}
SUBSETS = {"all": lambda c: np.ones_like(c, bool), "cohort": lambda c: c, "noncohort": lambda c: ~c}
NC = D.num_courses
for pr in metas:
    say(f"  {pr}: n={len(cohort[pr])}  cohort={cohort[pr].sum()}  non-cohort={(~cohort[pr]).sum()}")

R = ROOT / "results"
SEEDS = [42, 101, 202, 7, 13, 21, 34, 55, 89, 144]
# display name -> (family, per-user file pattern, recorded per-seed csv, key column value in that csv)
SEEDED = {
    "LSTM+attn (A, paper)": ("Recurrent", "e5_peruser/A_custom_attention_seed{s}.npz", "e5_attention.csv", "variant", "A_custom_attention"),
    "LSTM no attn (B)": ("Recurrent", "e5_peruser/B_no_attention_seed{s}.npz", "e5_attention.csv", "variant", "B_no_attention"),
    "LSTM+Keras MHA (C)": ("Recurrent", "e5_peruser/C_keras_mha_seed{s}.npz", "e5_attention.csv", "variant", "C_keras_mha"),
    "GRU4Rec": ("Recurrent", "e3_peruser/gru4rec_course_only_seed{s}.npz", "e3.csv", "model", "gru4rec_course_only"),
    "GRU4Rec+TA": ("Recurrent", "e3b_peruser/gru4rec_ta_course_only_seed{s}.npz", "e3b.csv", "model", "gru4rec_ta_course_only"),
    "GRU4Rec+feat": ("Recurrent", "e3_peruser/gru4rec_full_features_seed{s}.npz", "e3.csv", "model", "gru4rec_full_features"),
    "SASRec": ("Transformer", "e4_peruser/sasrec_course_only_seed{s}.npz", "e4.csv", "model", "sasrec_course_only"),
    "SASRec+TA": ("Transformer", "e4b_peruser/sasrec_ta_course_only_seed{s}.npz", "e4b.csv", "model", "sasrec_ta_course_only"),
    "SASRec+feat": ("Transformer", "e4_peruser/sasrec_full_features_seed{s}.npz", "e4.csv", "model", "sasrec_full_features"),
}
# budget-matched Optuna runs: E7 (objective = validation Hit@10) and E7b (objective = mean of default and strict validation Hit@10)
TUNED = [("LSTM no attn", "lstm_noattn", "Recurrent"), ("LSTM+attn (paper)", "lstm_attn", "Recurrent"), ("LSTM+Keras MHA", "lstm_mha", "Recurrent"),
         ("GRU4Rec", "gru4rec", "Recurrent"), ("GRU4Rec+TA", "gru4rec_ta", "Recurrent"), ("SASRec", "sasrec", "Transformer"), ("SASRec+TA", "sasrec_ta", "Transformer")]
SETOF = {nm: "E3-E5" for nm in SEEDED}; STATS_NAME = {}
for tag in ("e7", "e7b"):
    for disp, key, fm in TUNED:
        if not (R / f"{tag}_peruser/{key}_tuned_seed42.npz").exists(): continue
        nm = f"{disp} [{tag.upper()}]"
        SEEDED[nm] = (fm, f"{tag}_peruser/{key}_tuned_seed{{s}}.npz", f"{tag}.csv", "model", f"{key}_tuned"); SETOF[nm] = tag.upper()
        STATS_NAME[nm] = (tag, disp.replace(" (paper)", "") + " (tuned)")
FIXED = {"Popularity": ("Non-neural", "e1_markov_peruser.npz", "popularity", "e1_markov.csv", "model", "popularity"),
         "Markov 1st": ("Non-neural", "e1_markov_peruser.npz", "markov_1st", "e1_markov.csv", "model", "markov_1st"),
         "Markov+ctx 2nd": ("Non-neural", "e2_markov_ctx_peruser.npz", "markov_ctx_2nd", "e2_markov_ctx.csv", "model", "markov_ctx_2nd")}
SETOF.update({nm: "baseline" for nm in FIXED})
PU = ["hit1", "hit5", "hit10", "rr10", "ndcg10"]
REC = {"hit1": "Hit@1", "hit5": "Hit@5", "hit10": "Hit@10", "rr10": "MRR@10", "ndcg10": "NDCG@10"}
MET_NAMES = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10", "Coverage@10"]


def hitk_curve(top, y):
    m = top == y[:, None]
    return np.stack([m[:, :k].any(1).astype(float) for k in range(1, 11)], 1)       # n x 10


def coverage(top):
    return len(np.unique(top[:, :10])) / (NC - 1)


say("STEP 2  loading per-user files, verifying user order, recomputing metrics")
seed_rows, hitk, att_rows, att_len, xc = [], [], [], [], []
fam, src, params = {}, {}, {}
for nm, (fm, pat, rec_csv, key, keyval) in SEEDED.items():
    rec = pd.read_csv(R / rec_csv); rec = rec[rec[key] == keyval]
    fam[nm], src[nm] = fm, f"{pat.split('/')[0]}/ + {rec_csv}"
    params[nm] = int(rec["params"].iloc[0]); assert rec["params"].nunique() == 1, f"{nm}: params differ between seeds"
    maxdiff, ncmp, hk = 0.0, 0, {pr: [] for pr in metas}
    for s in SEEDS:
        z = np.load(R / pat.format(s=s))
        for pr in metas:
            assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {nm} seed {s} {pr}"
            y, top = z[f"{pr}_y"], z[f"{pr}_top10"]
            pu = {m: z[f"{pr}_{m}"] for m in PU}
            hk[pr].append(hitk_curve(top, y))
            for sub, f in SUBSETS.items():
                msk = f(cohort[pr]); r = {"model": nm, "family": fm, "seed": s, "protocol": pr, "subset": sub, "n": int(msk.sum())}
                for m in PU: r[REC[m]] = pu[m][msk].mean()
                r["Coverage@10"] = coverage(top[msk]); seed_rows.append(r)
            # exact cross-check against the experiment's own per-seed record (all users)
            row = rec[(rec.seed == s) & (rec.protocol == pr)]; assert len(row) == 1, f"{nm} {s} {pr}: {len(row)} recorded rows"
            for m in PU:
                maxdiff = max(maxdiff, abs(pu[m].mean() - float(row[REC[m]].iloc[0]))); ncmp += 1
            maxdiff = max(maxdiff, abs(coverage(top) - float(row["Coverage@10"].iloc[0]))); ncmp += 1
            # attention diagnostics (all users, only models that log them)
            if f"att_entropy_ratio" in z.files and pr == "default":
                uw = z["att_uniform_weight"]; ok = uw < 1 - 1e-9                       # history length >= 2
                att_rows.append({"model": nm, "seed": s, "n_users": int(ok.sum()), "entropy_ratio": z["att_entropy_ratio"][ok].mean(),
                                 "max_weight": z["att_max_weight"][ok].mean(), "uniform_weight": uw[ok].mean(),
                                 "last_pos_weight": z["att_last_pos_weight"][ok].mean(),
                                 "max_over_uniform": (z["att_max_weight"][ok] / uw[ok]).mean(),
                                 "last_over_uniform": (z["att_last_pos_weight"][ok] / uw[ok]).mean()})
                nlen = np.rint(1 / uw[ok]).astype(int)
                for n_ in np.unique(nlen):
                    q = nlen == n_
                    att_len.append({"model": nm, "seed": s, "history_len": int(n_), "n_users": int(q.sum()), "uniform_weight": uw[ok][q].mean(),
                                    "last_pos_weight": z["att_last_pos_weight"][ok][q].mean(), "max_weight": z["att_max_weight"][ok][q].mean()})
    for pr in metas:
        a = np.stack(hk[pr])                                                              # seeds x n x 10
        for k in range(10):
            sm = a[:, :, k].mean(1)
            hitk.append({"model": nm, "protocol": pr, "k": k + 1, "mean": sm.mean(), "min": sm.min(), "max": sm.max()})
    xc.append({"model": nm, "recorded_in": rec_csv, "n_values_compared": ncmp, "max_abs_diff": maxdiff}); say(f"  {nm:24s} seeds={len(SEEDS)}  max|recomputed-recorded|={maxdiff:.2e}")
for nm, (fm, fn, key, rec_csv, kcol, kval) in FIXED.items():
    z = np.load(R / fn); rec = pd.read_csv(R / rec_csv); rec = rec[rec[kcol] == kval]
    fam[nm], src[nm], params[nm] = fm, f"{fn} + {rec_csv}", np.nan
    maxdiff, ncmp = 0.0, 0
    for pr in metas:
        assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {nm}"
        pu = {m: z[f"{key}_{pr}_{m}"] for m in PU}
        top = z[f"{key}_{pr}_top10"] if f"{key}_{pr}_top10" in z.files else None
        y = z[f"{key}_{pr}_y"] if f"{key}_{pr}_y" in z.files else (z[f"{pr}_y"] if f"{pr}_y" in z.files else None)
        for sub, f in SUBSETS.items():
            msk = f(cohort[pr]); r = {"model": nm, "family": fm, "seed": -1, "protocol": pr, "subset": sub, "n": int(msk.sum())}
            for m in PU: r[REC[m]] = pu[m][msk].mean()
            r["Coverage@10"] = coverage(top[msk]) if top is not None else np.nan; seed_rows.append(r)
        if top is not None and y is not None:
            a = hitk_curve(top, y)
            for k in range(10): hitk.append({"model": nm, "protocol": pr, "k": k + 1, "mean": a[:, k].mean(), "min": a[:, k].mean(), "max": a[:, k].mean()})
        row = rec[rec.protocol == pr]; assert len(row) == 1, f"{nm} {pr}: {len(row)} recorded rows"
        for m in PU:
            maxdiff = max(maxdiff, abs(pu[m].mean() - float(row[REC[m]].iloc[0]))); ncmp += 1
        if top is not None:
            maxdiff = max(maxdiff, abs(coverage(top) - float(row["Coverage@10"].iloc[0]))); ncmp += 1
    xc.append({"model": nm, "recorded_in": rec_csv, "n_values_compared": ncmp, "max_abs_diff": maxdiff}); say(f"  {nm:24s} deterministic  max|recomputed-recorded|={maxdiff:.2e}")
XC = pd.DataFrame(xc)
assert (XC.max_abs_diff < 1e-9).all(), "RECOMPUTED VALUES DO NOT MATCH THE RECORDED RUNS:\n" + XC.to_string()
say("  PASS: every recomputed per-seed value equals the experiment's own record (tolerance 1e-9)")

ps = pd.DataFrame(seed_rows)
ps.to_csv(R / "p4_per_seed.csv", index=False)
pd.DataFrame(hitk).to_csv(R / "p4_hitk_curves.csv", index=False)
pd.DataFrame(att_rows).to_csv(R / "p4_attention_diag.csv", index=False)
pd.DataFrame(att_len).to_csv(R / "p4_attention_by_len.csv", index=False)

say("STEP 3  results_master.csv")
long = ps.melt(id_vars=["model", "family", "seed", "protocol", "subset", "n"], value_vars=MET_NAMES, var_name="metric", value_name="value")
g = long.groupby(["model", "family", "protocol", "subset", "metric"], sort=False)
mm = g["value"].agg(mean="mean", sd=lambda v: v.std(ddof=1) if len(v) > 1 else np.nan, min="min", max="max", n_seeds="count").reset_index()
mm["n_users"] = g["n"].first().values
mm["set"] = mm["model"].map(SETOF); mm["params"] = mm["model"].map(params); mm["source"] = mm["model"].map(src)
order = list(SEEDED) + list(FIXED)
mm["_o"] = mm["model"].map({m: i for i, m in enumerate(order)}); mm = mm.sort_values(["_o", "protocol", "subset", "metric"]).drop(columns="_o")
mm.to_csv(R / "results_master.csv", index=False)
say(f"  results_master.csv: {len(mm)} rows, {mm.model.nunique()} models")

say("STEP 4  cross-checks against E6 and X1 (independent code paths)")
e6 = pd.read_csv(R / "e6_models.csv")
for _, r in e6.iterrows():
    # e6 averages per-user outcomes over seeds first; mean over users of that = mean over seeds of per-seed means (equal n per seed)
    for sub, col in (("all", "hit10_all"), ("noncohort", "hit10_noncohort"), ("cohort", "hit10_cohort")):
        v = mm[(mm.model == r["model"]) & (mm.protocol == r["protocol"]) & (mm.subset == sub) & (mm.metric == "Hit@10")]["mean"].iloc[0]
        assert abs(v - r[col]) < 1e-9, f"E6 mismatch {r['model']} {r['protocol']} {sub}: {v} vs {r[col]}"
say("  PASS: Hit@10 (all / cohort / non-cohort) equals e6_models.csv for every model and protocol")
ci = pd.read_csv(R / "e6_paired_ci.csv"); ci = ci[(ci.variant == "mean_all_seeds") & (ci.metric == "hit10")]
for _, r in ci.iterrows():
    f = lambda m: mm[(mm.model == m) & (mm.protocol == r["protocol"]) & (mm.subset == r["subset"]) & (mm.metric == "Hit@10")]["mean"].iloc[0]
    assert abs((f(r["a"]) - f(r["b"])) - r["diff"]) < 1e-9, f"E6 diff mismatch {r['a']} - {r['b']} {r['protocol']} {r['subset']}"
    assert r["ci_lo"] <= r["diff"] <= r["ci_hi"], f"diff outside its own CI: {r['a']} - {r['b']}"
say(f"  PASS: all {len(ci)} E6 Hit@10 point differences equal the difference of the master means, and lie inside their CIs")
for tag in ("e7", "e7b"):
    st = pd.read_csv(R / f"{tag}stats_models.csv")
    for nm, (t_, sname) in STATS_NAME.items():
        if t_ != tag: continue
        for pr in metas:
            r = st[(st.model == sname) & (st.protocol == pr)].iloc[0]
            for sub, col in (("all", "hit10_all"), ("noncohort", "hit10_noncohort")):
                v = mm[(mm.model == nm) & (mm.protocol == pr) & (mm["subset"] == sub) & (mm.metric == "Hit@10")]["mean"].iloc[0]
                assert abs(v - r[col]) < 1e-9, f"{tag}stats mismatch {nm} {pr} {sub}"
say("  PASS: Hit@10 (all / non-cohort) of every tuned model equals e7stats_models.csv / e7bstats_models.csv")
x1 = pd.read_csv(R / "x1_final_cohort_split.csv").set_index(["model", "protocol"])
for x, nm in (("sasrec_e4", "SASRec"), ("lstm_attn_e5", "LSTM+attn (A, paper)"), ("lstm_noattn_e5", "LSTM no attn (B)")):
    for pr in metas:
        for sub, col in (("all", "Hit@10_all"), ("cohort", "Hit@10_cohort"), ("noncohort", "Hit@10_noncohort")):
            v = mm[(mm.model == nm) & (mm.protocol == pr) & (mm.subset == sub) & (mm.metric == "Hit@10")]["mean"].iloc[0]
            assert abs(v - x1.loc[(x, pr), col]) < 1e-9, f"X1 cohort-split mismatch {nm} {pr} {sub}"
say("  PASS: cohort split equals x1_final_cohort_split.csv (computed independently in X1)")
# published summary tables (4-decimal) vs master
for csv, keycol, mp in (("e3_summary.csv", None, {"gru4rec_course_only": "GRU4Rec", "gru4rec_full_features": "GRU4Rec+feat"}),
                        ("e4_summary.csv", None, {"sasrec_course_only": "SASRec", "sasrec_full_features": "SASRec+feat"}),
                        ("e3b_summary.csv", None, {"gru4rec_ta_course_only": "GRU4Rec+TA"}),
                        ("e4b_summary.csv", None, {"sasrec_ta_course_only": "SASRec+TA"}),
                        ("e7_summary.csv", None, {f"{k}_tuned": f"{d} [E7]" for d, k, _ in TUNED}), ("e7b_summary.csv", None, {f"{k}_tuned": f"{d} [E7B]" for d, k, _ in TUNED}),
                        ("e5_attention_summary.csv", None, {"A_custom_attention": "LSTM+attn (A, paper)", "B_no_attention": "LSTM no attn (B)", "C_keras_mha": "LSTM+Keras MHA (C)"})):
    s = pd.read_csv(R / csv, header=None, skiprows=3)
    for _, r in s.iterrows():
        nm = mp.get(r[0]);
        if nm is None: continue
        for j, mname in ((6, "Hit@10"), (8, "MRR@10")):
            v = mm[(mm.model == nm) & (mm.protocol == r[1]) & (mm.subset == "all") & (mm.metric == mname)]["mean"].iloc[0]
            assert abs(v - float(r[j])) < 6e-5, f"summary mismatch {csv} {nm} {r[1]} {mname}: {v:.5f} vs {r[j]}"
say("  PASS: seed means equal the rounded numbers printed in e3/e3b/e4/e4b/e5 summary files (Hit@10 and MRR@10)")
XC.to_csv(R / "p4_crosscheck.csv", index=False)

meta_out = {"seeds": SEEDS, "n_users": {pr: int(len(cohort[pr])) for pr in metas},
            "n_cohort": {pr: int(cohort[pr].sum()) for pr in metas}, "n_noncohort": {pr: int((~cohort[pr]).sum()) for pr in metas},
            "cohort_rule": "train-core history == (46, 47, 21): the fixed curriculum 46>47>21>52>60", "num_courses_in_coverage_denominator": int(NC - 1)}
(R / "p4_meta.json").write_text(json.dumps(meta_out, indent=2))
say("p4_build_master DONE")
