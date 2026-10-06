"""P4c - manuscript tables as csv, LaTeX (booktabs) and a json for the Word build.

Main tables use the budget-matched Optuna-tuned models of E7b; E7 (selection on default-protocol validation only) and the earlier lightly tuned E3-E5
models are in the supplement.  Every cell is formatted from results_master.csv, e7bstats_*.csv, e6_paired_ci.csv, x1_timeaudit_val.csv or the experiments'
own csv/json files; nothing is typed by hand.
Main : T1 performance, T2 paired differences, T3 cohort split.
Supp : S1 all metrics (E7b + baselines), S2 all metrics (E7), S3 all metrics (E3-E5), S4 paired differences for Hit@10/Hit@1/MRR@10 (E7b), S5 seed-89 and seed-level
       sensitivity (E7b), S6 tuning details (E3-E5 starting point, E7, E7b), S7 forward-time audit, S8 paired differences of the earlier E3-E5 models.
Outputs: results/tables/{T1..T3,S1..S8}.csv|.tex, results/tables/tables.json
Run: python experiment-2-revision/experiments/p4_make_tables.py     (after p4_build_master.py and e7_paired_ci.py --tuned-tag e7b)
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]; R = ROOT / "results"; OUT = R / "tables"; OUT.mkdir(exist_ok=True)
mm = pd.read_csv(R / "results_master.csv"); meta = json.loads((R / "p4_meta.json").read_text())
cb = pd.read_csv(R / "e7bstats_paired_ci.csv"); sb = pd.read_csv(R / "e7bstats_seed_level.csv")
c6 = pd.read_csv(R / "e6_paired_ci.csv"); ta = pd.read_csv(R / "x1_timeaudit_val.csv")
best = {t: json.loads((R / f"{t}_best.json").read_text()) for t in ("e7", "e7b")}; trials = {t: pd.read_csv(R / f"{t}_trials.csv") for t in ("e7", "e7b")}
MINUS = "−"; TABLES = []

BASE = ["Popularity", "Markov 1st", "Markov+ctx 2nd"]
KEYS = [("LSTM no attn", "LSTM, no attention"), ("LSTM+attn (paper)", "LSTM + attention (paper)"), ("GRU4Rec", "GRU4Rec"), ("GRU4Rec+TA", "GRU4Rec + TA"), ("SASRec", "SASRec"), ("SASRec+TA", "SASRec + TA")]
E7B = [f"{k} [E7B]" for k, _ in KEYS]; E7 = [f"{k} [E7]" for k, _ in KEYS] + ["LSTM+Keras MHA [E7]"]
LEG = ["LSTM no attn (B)", "LSTM+attn (A, paper)", "LSTM+Keras MHA (C)", "GRU4Rec", "GRU4Rec+TA", "GRU4Rec+feat", "SASRec", "SASRec+TA", "SASRec+feat"]
LABEL = {"Popularity": "Popularity", "Markov 1st": "Markov (1st order)", "Markov+ctx 2nd": "Markov + context (2nd order)",
         "LSTM no attn (B)": "LSTM, no attention", "LSTM+attn (A, paper)": "LSTM + attention (paper)", "LSTM+Keras MHA (C)": "LSTM + Keras MHA", "GRU4Rec": "GRU4Rec", "GRU4Rec+TA": "GRU4Rec + TA",
         "GRU4Rec+feat": "GRU4Rec + features", "SASRec": "SASRec", "SASRec+TA": "SASRec + TA", "SASRec+feat": "SASRec + features", "LSTM+Keras MHA [E7]": "LSTM + Keras MHA"}
for k, lab in KEYS:
    for t in ("E7B", "E7"): LABEL[f"{k} [{t}]"] = lab


def row(model, pr, sub, metric):
    r = mm[(mm.model == model) & (mm.protocol == pr) & (mm["subset"] == sub) & (mm.metric == metric)]; assert len(r) == 1, (model, pr, sub, metric); return r.iloc[0]


def ms(model, pr, sub, metric, d=4, sd=True):
    r = row(model, pr, sub, metric)
    return f"{r['mean']:.{d}f}" + (f" ± {r['sd']:.{d}f}" if sd and not np.isnan(r["sd"]) else "")


def pp(x, d=2):
    return f"{x * 100:+.{d}f}".replace("-", MINUS)


def pfmt(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def add(tid, title, header, rows, notes, bold=None, landscape=False, groups=None):
    TABLES.append({"id": tid, "title": title, "header": header, "rows": rows, "notes": notes, "bold": sorted(bold or []), "landscape": landscape, "groups": groups})
    flat = header[-1] if isinstance(header[0], list) else header
    pd.DataFrame(rows, columns=flat).to_csv(OUT / f"{tid}.csv", index=False)
    tex = ["\\begin{table}[t]\\centering\\footnotesize", f"\\caption{{{title}}}", "\\begin{tabular}{l" + "c" * (len(flat) - 1) + "}\\toprule"]
    for h in (header if isinstance(header[0], list) else [header]): tex.append(" & ".join(h) + " \\\\")
    tex.append("\\midrule")
    bs = set(map(tuple, bold or []))
    for i, r in enumerate(rows):
        tex.append(" & ".join((f"\\textbf{{{c}}}" if (i, j) in bs else c) for j, c in enumerate(r)).replace("±", "$\\pm$").replace(MINUS, "$-$") + " \\\\")
    tex += ["\\bottomrule", "\\end{tabular}", f"\\par\\smallskip\\footnotesize {notes}", "\\end{table}"]
    (OUT / f"{tid}.tex").write_text("\n".join(tex).replace("%", "\\%").replace("_", "\\_"))


NU = meta["n_users"]; NC = meta["n_cohort"]; NN = meta["n_noncohort"]
SEEDLIST = "42, 101, 202, 7, 13, 21, 34, 55, 89, 144"

# ---- Table 1 ---------------------------------------------------------------------------------------------------------------------------
cols = [("default", "all", "Hit@10"), ("default", "all", "MRR@10"), ("strict", "all", "Hit@10"), ("strict", "all", "MRR@10"), ("strict", "noncohort", "Hit@10")]
ORD = BASE + E7B; rows, vals = [], []
for m in ORD:
    p = row(m, "default", "all", "Hit@10")["params"]
    rows.append([LABEL[m] + (" †" if m in BASE else ""), "–" if np.isnan(p) else f"{int(p):,}"] + [ms(m, *c) for c in cols]); vals.append([row(m, *c)["mean"] for c in cols])
vals = np.array(vals); bold = set()
for j in range(len(cols)):
    top = np.round(vals[:, j], 4).max()
    for i in range(len(ORD)):
        if round(vals[i, j], 4) == top: bold.add((i, j + 2))
add("T1", "Test performance of the baselines and the six tuned neural models under the default and strict protocols",
    [["Model", "Parameters", "Default protocol", "", "Strict protocol", "", "Strict, non-cohort users"], ["", "", "Hit@10", "MRR@10", "Hit@10", "MRR@10", "Hit@10"]], rows,
    f"Mean ± standard deviation over ten training seeds ({SEEDLIST}); test users n = {NU['default']:,} (default) and {NU['strict']:,} (strict); non-cohort users n = {NN['strict']:,}. "
    "Best value per column in bold. † Deterministic: no seed variation. Every neural model received the same hyperparameter search (30 Optuna trials, objective = mean of default and strict validation "
    "Hit@10, selection on validation users only; Table S6) and was then trained once per seed and evaluated once on the test set. Data, split, 60-course vocabulary and full-history masking are shared by all models. "
    "TA, the paper's temporal-attention pooling. Results for the earlier small-grid models and for a search selected on default-protocol validation only are in Tables S2 and S3.", bold=bold, groups=[(2, 3), (4, 5)])

# ---- Table 2 ---------------------------------------------------------------------------------------------------------------------------
c0 = cb[(cb.variant == "mean_all_seeds") & (cb.metric == "hit10")]
tn = lambda k: f"{k} (tuned)"
CONTR = [("Backbone, without TA", None, None), (tn("SASRec"), tn("LSTM no attn"), "SASRec − LSTM"), (tn("GRU4Rec"), tn("LSTM no attn"), "GRU4Rec − LSTM"), (tn("SASRec"), tn("GRU4Rec"), "SASRec − GRU4Rec"),
         ("Backbone, with TA", None, None), (tn("SASRec+TA"), tn("LSTM+attn"), "SASRec + TA − LSTM + attention"), (tn("GRU4Rec+TA"), tn("LSTM+attn"), "GRU4Rec + TA − LSTM + attention"),
         (tn("SASRec+TA"), tn("GRU4Rec+TA"), "SASRec + TA − GRU4Rec + TA"),
         ("Temporal attention (with − without)", None, None), (tn("LSTM+attn"), tn("LSTM no attn"), "LSTM"), (tn("GRU4Rec+TA"), tn("GRU4Rec"), "GRU4Rec"), (tn("SASRec+TA"), tn("SASRec"), "SASRec"),
         ("Selection objective (E7b − E7)", None, None)] + [(tn(k), f"{k} (E7)", lab) for k, lab in (("LSTM no attn", "LSTM, no attention"), ("LSTM+attn", "LSTM + attention"), ("GRU4Rec", "GRU4Rec"),
                                                                                                          ("GRU4Rec+TA", "GRU4Rec + TA"), ("SASRec", "SASRec"), ("SASRec+TA", "SASRec + TA"))] + \
        [("Reference baselines", None, None), (tn("LSTM+attn"), "Markov 1st", "LSTM + attention − Markov (1st order)"), (tn("SASRec"), "Markov 1st", "SASRec − Markov (1st order)"),
         (tn("LSTM+attn"), "Popularity", "LSTM + attention − Popularity")]
rows, bold = [], set()
for a, b, lab in CONTR:
    if b is None: rows.append([a, "", "", "", "", "", ""]); continue
    r = [lab]
    for pr, sub in (("default", "all"), ("strict", "all"), ("strict", "noncohort")):
        x = c0[(c0.a == a) & (c0.b == b) & (c0.protocol == pr) & (c0["subset"] == sub)]; assert len(x) == 1, (a, b, pr, sub); x = x.iloc[0]
        r += [f"{pp(x['diff'])} [{pp(x.ci_lo)}, {pp(x.ci_hi)}]", pfmt(x.p_holm)]
        if x.significant_holm_05: bold.add((len(rows), len(r) - 2))
    rows.append(r)
nfam = len(c0[(c0.protocol == "default") & (c0["subset"] == "all")])
add("T2", "Paired differences in Hit@10 between the tuned models, with 95% bootstrap intervals",
    [["Comparison (first minus second)", "Default, all users", "", "Strict, all users", "", "Strict, non-cohort users", ""], ["", "Δ [95% CI]", "p (Holm)", "Δ [95% CI]", "p (Holm)", "Δ [95% CI]", "p (Holm)"]], rows,
    "Δ in percentage points of Hit@10; positive favours the first-named model. Per-user outcomes were averaged over the ten seeds, then 10,000 bootstrap resamples of test users gave percentile intervals; "
    f"p values are two-sided bootstrap p values adjusted by the Holm method within each protocol and user subset ({nfam} comparisons; 0.002 is the resolution limit of 10,000 resamples after adjustment). Bold: Holm-adjusted p < 0.05. "
    f"Non-cohort users exclude the {NC['default']:,} users whose history is the fixed curriculum 46→47→21. The E7 models were selected on default-protocol validation Hit@10 only. Other metrics: Table S4.",
    bold=bold, groups=[(1, 2), (3, 4), (5, 6)])

# ---- Table 3 ---------------------------------------------------------------------------------------------------------------------------
rows = [[LABEL[m]] + [ms(m, pr, sub, "Hit@10", sd=False) for pr in ("default", "strict") for sub in ("cohort", "noncohort", "all")] for m in ORD]
add("T3", "Hit@10 for cohort and non-cohort users",
    [["Model", "Default protocol", "", "", "Strict protocol", "", ""], ["", f"Cohort (n = {NC['default']:,})", f"Non-cohort (n = {NN['default']:,})", f"All (n = {NU['default']:,})",
      f"Cohort (n = {NC['strict']:,})", f"Non-cohort (n = {NN['strict']:,})", f"All (n = {NU['strict']:,})"]], rows,
    "Cohort users are those whose training history is exactly the curriculum prefix 46→47→21; the full curriculum is 46→47→21→52→60. Mean over ten seeds (single value for the deterministic baselines). "
    "Under the strict protocol the Markov models cannot reach course 60 from course 21 because course 52 (the validation target) is not in their history.", groups=[(1, 3), (4, 6)])

# ---- S1-S3 all metrics -----------------------------------------------------------------------------------------------------------------
mets = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10", "Coverage@10"]


def allmetrics(tid, title, models, note):
    rows = [[LABEL[m]] + [ms(m, pr, "all", k, sd=True) for pr in ("default", "strict") for k in mets] for m in models]
    add(tid, title, [["Model"] + ["Default protocol"] + [""] * 5 + ["Strict protocol"] + [""] * 5, [""] + mets + mets], rows,
        note + " Mean ± SD over ten seeds. Coverage@10 = distinct courses recommended in any top-10 list divided by 59 recommendable courses.", landscape=True, groups=[(1, 6), (7, 12)])


allmetrics("S1", "All metrics for the baselines and the six tuned neural models (E7b)", ORD, "Selection objective: mean of default and strict validation Hit@10. Deterministic baselines have no SD.")
allmetrics("S2", "All metrics for the models tuned on default-protocol validation Hit@10 only (E7)", E7, "Same search as E7b, objective = validation Hit@10 of the default protocol.")
allmetrics("S3", "All metrics for the earlier models with a small tuning grid (E3–E5)", LEG, "LSTM variants used the paper's fixed architecture; GRU4Rec and SASRec were tuned on a grid of 4 to 6 configurations (validation, seed 42).")

# ---- S4 multi-metric paired differences (E7b) ------------------------------------------------------------------------------------------
c_all = cb[cb.variant == "mean_all_seeds"]; rows, cur = [], ""
fmt = lambda x, met: (f"{pp(x['diff'])} [{pp(x.ci_lo)}, {pp(x.ci_hi)}]" if met != "rr10" else f"{x['diff']:+.4f} [{x.ci_lo:+.4f}, {x.ci_hi:+.4f}]".replace("-", MINUS)) + (" *" if x.significant_holm_05 else "")
for a, b, lab in CONTR:
    if b is None: cur = a; continue
    if cur == "Reference baselines": continue
    r = [f"{cur}: {lab}"]
    for met in ("hit10", "hit1", "rr10"):
        for pr in ("default", "strict"):
            x = c_all[(c_all.a == a) & (c_all.b == b) & (c_all.protocol == pr) & (c_all["subset"] == "all") & (c_all.metric == met)].iloc[0]; r.append(fmt(x, met))
    rows.append(r)
add("S4", "Paired differences for Hit@10, Hit@1 and MRR@10 between the tuned models (E7b, all users)",
    [["Comparison", "Hit@10 (pp)", "", "Hit@1 (pp)", "", "MRR@10 (reciprocal-rank units)", ""], ["", "Default", "Strict", "Default", "Strict", "Default", "Strict"]], rows,
    "Same method and comparisons as Table 2 (first minus second). * Holm-adjusted p < 0.05. MRR@10 under the strict protocol varies strongly between seeds for several models (SD up to 0.035; Table S1), "
    "so differences in that column should be read with caution. Machine-readable version with all subsets and p values: results/e7bstats_paired_ci.csv.", landscape=True, groups=[(1, 2), (3, 4), (5, 6)])

# ---- S5 sensitivity ---------------------------------------------------------------------------------------------------------------------
x89 = cb[(cb.variant == "mean_excl_seed89") & (cb.metric == "hit10") & (cb["subset"] == "all")]; rows, cur = [], ""
for a, b, lab in CONTR:
    if b is None: cur = a; continue
    if cur == "Reference baselines": continue
    r = [f"{cur}: {lab}"]
    for pr in ("default", "strict"):
        x = c0[(c0.a == a) & (c0.b == b) & (c0.protocol == pr) & (c0["subset"] == "all")].iloc[0]; y = x89[(x89.a == a) & (x89.b == b) & (x89.protocol == pr)].iloc[0]
        s_ = sb[(sb.a == a) & (sb.b == b) & (sb.protocol == pr)].iloc[0]
        r += [f"{pp(x['diff'])} ({'sig' if x.significant_holm_05 else 'n.s.'})", f"{pp(y['diff'])} ({'sig' if y.significant_holm_05 else 'n.s.'})",
              "yes" if bool(x.significant_holm_05) != bool(y.significant_holm_05) else "no", f"{int(s_.seeds_a_better)}/10"]
    rows.append(r)
add("S5", "Sensitivity of the paired Hit@10 differences (E7b) to seed 89 and to seed choice",
    [["Comparison", "Default protocol", "", "", "", "Strict protocol", "", "", ""], ["", "All 10 seeds", "Without seed 89", "Verdict changes", "Seeds won", "All 10 seeds", "Without seed 89", "Verdict changes", "Seeds won"]], rows,
    "Δ in percentage points, all users; sig = Holm-adjusted p < 0.05. Seeds won = number of seeds in which the first-named model has the higher Hit@10 (seed-level paired comparison, same seed for both models). "
    "Seed 89 is the seed in which the SASRec + features model of E4 failed under the strict protocol (Figure 3c).", landscape=True, groups=[(1, 4), (5, 8)])

# ---- S6 tuning details ---------------------------------------------------------------------------------------------------------------
SPACE = {"lstm": "course embedding {64, 96, 128}; competency embedding {16, 32}; latent units {128, 192, 256}; dropout 0.1–0.5; learning rate 3×10⁻⁴–3×10⁻³ (log)",
         "gru": "embedding {64, 96, 128}; units {64, 128, 192, 256}; dropout 0.1–0.5; learning rate 3×10⁻⁴–3×10⁻³ (log)",
         "sas": "d {64, 96, 128}; blocks {1, 2, 3}; heads {2, 4}; dropout 0.1–0.5; learning rate 3×10⁻⁴–3×10⁻³ (log)"}
KEY = {"LSTM no attn": "lstm_noattn", "LSTM+attn (paper)": "lstm_attn", "GRU4Rec": "gru4rec", "GRU4Rec+TA": "gru4rec_ta", "SASRec": "sasrec", "SASRec+TA": "sasrec_ta"}
fc = lambda c: ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in c.items())
rows = []
for tag, tlab in (("e7b", "E7b"), ("e7", "E7")):
    for k, lab in KEYS:
        b = best[tag][KEY[k]]; t = trials[tag]; t0 = t[(t.model == KEY[k]) & (t.trial == b["best_trial"])].iloc[0]       # parameter count of the SELECTED configuration
        rows.append([tlab, lab, str(b["n_trials"]), fc(b["cfg"]), f"{b['val_Hit@10_E3_E5_config']:.4f} → {b['val_Hit@10']:.4f}", f"{int(t0.params):,}"])
add("S6", "Hyperparameter search: selected configurations and validation objective", ["Search", "Model", "Trials", "Selected configuration", "Objective: E3–E5 start → selected", "Parameters"], rows,
    "Optuna with the TPE sampler (seed 0, multivariate), 30 trials per model, each trial scored as the mean over two training seeds (42, 101). Trial 0 is the configuration used in E3–E5, so the selected value can only "
    "match or exceed it on validation. Objective: E7b, mean of default and strict validation Hit@10 (strict validation set: 4,221 users whose training core has at least three courses, history without the last course); "
    "E7, validation Hit@10 of the default protocol. Search space (LSTM, with and without attention): " + SPACE["lstm"] + ". GRU4Rec (with and without TA): " + SPACE["gru"] + ". SASRec (with and without TA): " + SPACE["sas"] +
    ". All models: Adam, batch size 64, at most 50 epochs, early stopping on validation loss (patience 5), learning-rate halving on plateau. The Keras MHA variant was searched in E7 only.", landscape=True)

# ---- S7 forward-time audit -------------------------------------------------------------------------------------------------------------
DEFN = {"S0_base": "SASRec, course sequence only (125,437 parameters)", "T_gap": "+ time since the previous course as an input sequence", "C_calendar": "+ calendar month of the last course",
        "P_candprior": "+ additive logit prior from past enrolment counts (trending in 7 and 30 days, launched and age flags)", "TCP": "time gaps + calendar month + candidate prior",
        "Q_trend": "candidate prior with the two trending counts only", "Q4_trend_trans": "trending counts + recent a→b transition counts"}
bs = ta[ta.variant == "S0_base"].set_index("seed")["future_Hit@10"]; rows = []
for v in DEFN:
    d = ta[ta.variant == v].set_index("seed"); dl = (d["future_Hit@10"] - bs).dropna()
    rows.append([v, DEFN[v], str(len(d)), f"{d['future_Hit@1'].mean():.4f}", f"{d['future_Hit@10'].mean():.4f} ± {d['future_Hit@10'].std(ddof=1):.4f}" if len(d) > 1 else f"{d['future_Hit@10'].mean():.4f}",
                 f"{d['future_MRR@10'].mean():.4f}", "–" if v == "S0_base" else f"{pp(dl.mean(), 2)} ± {dl.std(ddof=1) * 100:.2f}"])
add("S7", "Forward-in-time audit (training before 2025-10-01, evaluation after)", ["Variant", "Definition", "Seeds", "Hit@1", "Hit@10", "MRR@10", "Paired Δ Hit@10 vs base (pp)"], rows,
    f"Trained on {int(ta.n_train.iloc[0]):,} sequence prefixes with target date before 2025-10-01; evaluated on {int(ta.n_future_eval.iloc[0]):,} validation users with target date on or after 2025-10-01. "
    "Validation, not test, users; seeds 7, 13, 42, 101, 202 (T_gap: three). The target date is never an input. Differences are paired by seed; ± is the SD of the paired differences. "
    "Stability of these variants under the strict protocol was not part of this audit.", landscape=True)

# ---- S8 legacy paired comparisons (E3-E5) --------------------------------------------------------------------------------------------
cl = c6[(c6.variant == "mean_all_seeds") & (c6.metric == "hit10")]; L = "LSTM+attn (A, paper)"
LC = [("SASRec", L, "SASRec − LSTM + attention (paper)"), ("GRU4Rec", L, "GRU4Rec − LSTM + attention (paper)"), ("SASRec", "GRU4Rec", "SASRec − GRU4Rec"),
      (L, "LSTM no attn (B)", "LSTM + attention − LSTM without attention"), (L, "LSTM+Keras MHA (C)", "LSTM + attention − LSTM + Keras MHA"), ("GRU4Rec+TA", "GRU4Rec", "GRU4Rec + TA − GRU4Rec"),
      ("SASRec+TA", "SASRec", "SASRec + TA − SASRec"), ("SASRec+feat", "SASRec", "SASRec + features − SASRec"), ("GRU4Rec+feat", "GRU4Rec", "GRU4Rec + features − GRU4Rec")]
rows, bold = [], set()
for a, b, lab in LC:
    r = [lab]
    for pr, sub in (("default", "all"), ("strict", "all"), ("strict", "noncohort")):
        x = cl[(cl.a == a) & (cl.b == b) & (cl.protocol == pr) & (cl["subset"] == sub)].iloc[0]
        r += [f"{pp(x['diff'])} [{pp(x.ci_lo)}, {pp(x.ci_hi)}]", pfmt(x.p_holm)]
        if x.significant_holm_05: bold.add((len(rows), len(r) - 2))
    rows.append(r)
add("S8", "Paired differences in Hit@10 for the earlier models with a small tuning grid (E3–E5)",
    [["Comparison (first minus second)", "Default, all users", "", "Strict, all users", "", "Strict, non-cohort users", ""], ["", "Δ [95% CI]", "p (Holm)", "Δ [95% CI]", "p (Holm)", "Δ [95% CI]", "p (Holm)"]], rows,
    "Same method as Table 2 (13 comparisons per Holm family, including reference baselines not shown). In these models the paper's LSTM had not been tuned while GRU4Rec and SASRec had; Table 2 repeats the "
    "comparison after equal tuning and the sign of several differences changes (Figure S3). Bold: Holm-adjusted p < 0.05.", bold=bold, groups=[(1, 2), (3, 4), (5, 6)])

(OUT / "tables.json").write_text(json.dumps(TABLES, ensure_ascii=False, indent=1))
print("wrote", [t["id"] for t in TABLES])
