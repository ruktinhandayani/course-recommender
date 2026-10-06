"""P4b - manuscript figures (Okabe-Ito palette, vector PDF + 600 dpi PNG) and data-driven captions.

Main results use the budget-matched, Optuna-tuned models of E7b (objective = mean of validation Hit@10 and validation-strict Hit@10); E7 (objective =
validation Hit@10) and the earlier lightly tuned E3-E5 models appear in Figure S3 and the supplementary tables.
Reads ONLY csv/json written by p4_build_master.py, e7_paired_ci.py (both cross-checked against the recorded runs) and x1_timeaudit_val.csv.
No number is typed by hand: annotations and captions are formatted from data.
Outputs: results/figures/Fig{1..4}_*.pdf|png, FigS{1,2,3}_*.pdf|png, figure_captions.md, figure_manifest.csv
Run: python experiment-2-revision/experiments/p4_make_figures.py     (run p4_build_master.py and e7_paired_ci.py --tuned-tag e7b first)
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"; OUT = R / "figures"; OUT.mkdir(exist_ok=True)
for need in ("results_master.csv", "p4_per_seed.csv", "p4_hitk_curves.csv", "p4_attention_diag.csv", "p4_attention_by_len.csv", "e7bstats_paired_ci.csv",
             "x1_timeaudit_val.csv", "p4_meta.json"):
    if not (R / need).exists(): sys.exit(f"missing {need}: run p4_build_master.py / e7_paired_ci.py first")
mm = pd.read_csv(R / "results_master.csv"); ps = pd.read_csv(R / "p4_per_seed.csv"); hk = pd.read_csv(R / "p4_hitk_curves.csv")
att = pd.read_csv(R / "p4_attention_diag.csv"); attl = pd.read_csv(R / "p4_attention_by_len.csv")
ci = pd.read_csv(R / "e7bstats_paired_ci.csv"); ta = pd.read_csv(R / "x1_timeaudit_val.csv"); meta = json.loads((R / "p4_meta.json").read_text())

# ---- style ------------------------------------------------------------------------------------------------------------------------------
OI = dict(black="#000000", orange="#E69F00", sky="#56B4E9", green="#009E73", yellow="#F0E442", blue="#0072B2", verm="#D55E00", purple="#CC79A7")
GREY, LIGHT = "#6B6B6B", "#E4E4E4"
fam_font = "Arial" if any("Arial" == f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
plt.rcParams.update({"font.family": fam_font, "font.size": 7, "axes.labelsize": 7.5, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6.5,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 600,
                     "axes.axisbelow": True, "legend.frameon": False, "axes.unicode_minus": True})
W2 = 7.0           # double-column width, inches (about 178 mm)
MANIFEST, CAP = [], {}

# ---- models ------------------------------------------------------------------------------------------------------------------------------
B = "[E7B]"
M_LN, M_LA, M_GR, M_GT, M_SA, M_ST = (f"LSTM no attn {B}", f"LSTM+attn (paper) {B}", f"GRU4Rec {B}", f"GRU4Rec+TA {B}", f"SASRec {B}", f"SASRec+TA {B}")
BASE = ["Popularity", "Markov 1st", "Markov+ctx 2nd"]
GROUPS = [("Non-neural", BASE), ("LSTM", [M_LN, M_LA]), ("GRU4Rec", [M_GR, M_GT]), ("SASRec", [M_SA, M_ST])]
GCOL = {"Non-neural": OI["black"], "LSTM": OI["blue"], "GRU4Rec": OI["green"], "SASRec": OI["verm"]}
MCOL = {m: GCOL[g] for g, ms in GROUPS for m in ms}
LABEL = {"Popularity": "Popularity", "Markov 1st": "Markov (1st order)", "Markov+ctx 2nd": "Markov + context (2nd order)", M_LN: "LSTM, no attention", M_LA: "LSTM + attention (paper)",
         M_GR: "GRU4Rec", M_GT: "GRU4Rec + TA", M_SA: "SASRec", M_ST: "SASRec + TA"}
NEURAL = [M_LN, M_LA, M_GR, M_GT, M_SA, M_ST]
SEEDS = meta["seeds"]


def M(model, pr, sub, metric, col="mean"):
    r = mm[(mm.model == model) & (mm.protocol == pr) & (mm["subset"] == sub) & (mm.metric == metric)]
    assert len(r) == 1, (model, pr, sub, metric, len(r)); return float(r[col].iloc[0])


def panel(ax, letter, dx=0.0, dy=1.02):
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="right")


def save(fig, stem, desc, sources):
    for ext in ("pdf", "png"): fig.savefig(OUT / f"{stem}.{ext}", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig); MANIFEST.append({"figure": stem, "content": desc, "data_sources": sources}); print("wrote", stem)


def pp(x, d=1, sign=True):
    s = f"{x * 100:+.{d}f}" if sign else f"{x * 100:.{d}f}"
    return s.replace("-", "−")


# =====================================================================================================================================
# Figure 1: protocol gap
# =====================================================================================================================================
fig = plt.figure(figsize=(W2, 3.35))
gs = fig.add_gridspec(2, 2, width_ratios=[1.28, 1], height_ratios=[1, 1], wspace=0.30, hspace=0.42, left=0.22, right=0.99, top=0.865, bottom=0.11)
axA = fig.add_subplot(gs[:, 0]); axB = fig.add_subplot(gs[0, 1]); axC = fig.add_subplot(gs[1, 1])
ypos, y, bands = {}, 0, []
for gi, (g, ms) in enumerate(GROUPS):
    y0 = y
    for m in ms: ypos[m] = y; y += 1
    bands.append((g, y0 - 0.5, y - 0.5)); y += 0.55
ymax = y - 0.55 - 0.5
for gi, (g, lo, hi) in enumerate(bands):
    if gi % 2 == 0: axA.axhspan(lo, hi, color="#F4F4F4", lw=0, zorder=0)
    axA.text(0.255, lo + 0.12, g, fontsize=6, color=GREY, va="top", ha="left", style="italic")
for m, yy in ypos.items():
    c = MCOL[m]; d, s_ = M(m, "default", "all", "Hit@10"), M(m, "strict", "all", "Hit@10")
    axA.plot([s_, d], [yy, yy], color=c, lw=1.1, zorder=2, solid_capstyle="butt")
    sd = ps[(ps.model == m) & (ps["subset"] == "all") & (ps.seed >= 0)]
    if len(sd):
        rng = np.random.default_rng(1)
        for pr in ("default", "strict"):
            v = sd[sd.protocol == pr]["Hit@10"].values
            axA.scatter(v, yy + rng.uniform(-0.17, 0.17, len(v)), s=2.2, color=c, alpha=0.35, lw=0, zorder=3)
    axA.scatter([d], [yy], s=22, facecolor="white", edgecolor=c, lw=1.0, zorder=4)
    axA.scatter([s_], [yy], s=22, facecolor=c, edgecolor=c, lw=1.0, zorder=4)
    axA.text(1.0, yy, pp(s_ - d), ha="right", va="center", fontsize=6.3, color="black")
axA.text(1.0, -1.05, "Δ (pp)", ha="right", va="center", fontsize=6.3, color=GREY)
axA.set_ylim(ymax + 0.15, -1.45); axA.set_xlim(0.25, 1.0)
axA.set_yticks(list(ypos.values())); axA.set_yticklabels([LABEL[m] for m in ypos]); axA.tick_params(axis="y", length=0)
axA.set_xlabel("Hit@10 (mean of 10 seeds; dots = single seeds)"); axA.xaxis.grid(True, color=LIGHT, lw=0.5); axA.spines["left"].set_visible(False)
axA.legend(handles=[Line2D([], [], marker="o", ls="", mfc="white", mec="black", ms=4.6, label="default protocol"),
                    Line2D([], [], marker="o", ls="", mfc="black", mec="black", ms=4.6, label="strict protocol")], loc="lower left", bbox_to_anchor=(0.0, 0.0), borderaxespad=0.2, handletextpad=0.2)
panel(axA, "a", dx=-0.60)
KEYM = ["Popularity", "Markov 1st", M_LA, M_GR, M_SA]
STY = {"Popularity": "dotted", "Markov 1st": "dashed", M_LA: "solid", M_GR: "solid", M_SA: "solid"}
for ax, pr, let in ((axB, "default", "b"), (axC, "strict", "c")):
    for m in KEYM:
        h = hk[(hk.model == m) & (hk.protocol == pr)].sort_values("k")
        ax.fill_between(h.k, h["min"], h["max"], color=MCOL[m], alpha=0.18, lw=0); ax.plot(h.k, h["mean"], color=MCOL[m], ls=STY[m], lw=1.1)
    ax.set_xlim(1, 10); ax.set_ylim(0, 1.0); ax.set_xticks(range(1, 11)); ax.yaxis.grid(True, color=LIGHT, lw=0.5)
    ax.set_ylabel(f"Hit@k, {pr}"); panel(ax, let, dx=-0.17, dy=1.03)
axC.set_xlabel("k (list length)")
fig.legend(handles=[Line2D([], [], color=MCOL[m], ls=STY[m], lw=1.2, label=LABEL[m]) for m in KEYM], loc="upper left", ncol=3, bbox_to_anchor=(0.585, 1.0), handlelength=1.8, labelspacing=0.3, columnspacing=1.0)
save(fig, "Fig1_protocol_gap", "Hit@10 under both protocols for the baselines and the six tuned neural models, and Hit@k curves", "results_master.csv, p4_per_seed.csv, p4_hitk_curves.csv")
dr = {m: M(m, "strict", "all", "Hit@10") - M(m, "default", "all", "Hit@10") for m in ypos}
nd = [dr[m] for m in NEURAL]
CAP["Fig1"] = (f"**Figure 1. Strict evaluation costs the neural models {abs(max(nd)) * 100:.1f} to {abs(min(nd)) * 100:.1f} Hit@10 points and the Markov baseline {abs(dr['Markov 1st']) * 100:.0f}.** "
    f"(a) Hit@10 on {meta['n_users']['default']:,} test users (default protocol, open circles) and {meta['n_users']['strict']:,} (strict protocol, filled circles) for the non-neural baselines and the six neural models after "
    f"budget-matched hyperparameter search (E7b); large markers are means of ten seeds (42, 101, 202, 7, 13, 21, 34, 55, 89, 144), small dots are single seeds, and the right-hand column gives strict minus default in percentage points. "
    f"Popularity and the Markov models are deterministic. (b, c) Hit@k for k = 1 to 10 under the default and strict protocols; bands span the lowest and highest seed. "
    f"TA, the paper's temporal-attention pooling over the recurrent or self-attention states.")

# =====================================================================================================================================
# Figure 2: paired differences (forest plot), tuned models (E7b)
# =====================================================================================================================================
T = lambda k: f"{k} (tuned)"
LN, LA, GR, GT, SA, ST = T("LSTM no attn"), T("LSTM+attn"), T("GRU4Rec"), T("GRU4Rec+TA"), T("SASRec"), T("SASRec+TA")
ROWS = [("Backbone, without TA", [(SA, LN, "SASRec − LSTM"), (GR, LN, "GRU4Rec − LSTM"), (SA, GR, "SASRec − GRU4Rec")]),
        ("Backbone, with TA", [(ST, LA, "SASRec + TA − LSTM + attention"), (GT, LA, "GRU4Rec + TA − LSTM + attention"), (ST, GT, "SASRec + TA − GRU4Rec + TA")]),
        ("Temporal attention", [(LA, LN, "LSTM: with − without"), (GT, GR, "GRU4Rec: with − without"), (ST, SA, "SASRec: with − without")]),
        ("Selection objective (E7b − E7)", [(T(k), f"{k} (E7)", lab) for k, lab in (("LSTM no attn", "LSTM, no attention"), ("LSTM+attn", "LSTM + attention"), ("GRU4Rec", "GRU4Rec"),
                                                                                        ("GRU4Rec+TA", "GRU4Rec + TA"), ("SASRec", "SASRec"), ("SASRec+TA", "SASRec + TA"))])]
c0 = ci[(ci.variant == "mean_all_seeds") & (ci.metric == "hit10")]


def crow(a, b, pr, sub):
    r = c0[(c0.a == a) & (c0.b == b) & (c0.protocol == pr) & (c0["subset"] == sub)]; assert len(r) == 1, (a, b, pr, sub); return r.iloc[0]


yy, ylab, hdr = 0, [], []
for g, items in ROWS:
    hdr.append((yy, g)); yy += 1
    for a, b, lab in items: ylab.append((yy, a, b, lab)); yy += 1
    yy += 0.35
fig = plt.figure(figsize=(W2, 4.7))
gs = fig.add_gridspec(1, 2, wspace=0.07, left=0.30, right=0.99, top=0.945, bottom=0.115)
axs = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
for ax, pr in zip(axs, ("default", "strict")):
    allr = [crow(a, b, pr, s) for _, a, b, _ in ylab for s in ("all", "noncohort")]
    lo, hi = min(r.ci_lo for r in allr) * 100 - 0.15, max(r.ci_hi for r in allr) * 100 + 0.15
    ax.axvline(0, color=GREY, lw=0.7, ls=(0, (3, 2)), zorder=1)
    for (y_, a, b, _) in ylab:
        for sub, col, mk, off in (("all", OI["black"], "o", -0.16), ("noncohort", OI["orange"], "s", 0.16)):
            r = crow(a, b, pr, sub); sig = bool(r.significant_holm_05)
            ax.plot([r.ci_lo * 100, r.ci_hi * 100], [y_ + off] * 2, color=col, lw=1.0, solid_capstyle="butt", zorder=2)
            ax.scatter([r["diff"] * 100], [y_ + off], s=15, marker=mk, facecolor=col if sig else "white", edgecolor=col, lw=0.9, zorder=3)
    ax.set_ylim(yy - 0.45, -0.7); ax.set_xlim(lo, hi); ax.xaxis.grid(True, color=LIGHT, lw=0.5); ax.set_xlabel("Δ Hit@10 (percentage points)")
axs[0].set_yticks([y_ for y_, *_ in ylab]); axs[0].set_yticklabels([t for *_, t in ylab]); axs[0].tick_params(axis="y", length=0)
axs[1].set_yticks([]); axs[1].spines["left"].set_visible(False)
for y_, g in hdr: axs[0].text(-0.62, y_, g, transform=axs[0].get_yaxis_transform(), ha="right", va="center", fontsize=7, fontweight="bold")
axs[0].text(0.0, 1.015, "a  default protocol", transform=axs[0].transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
axs[1].text(0.0, 1.015, "b  strict protocol", transform=axs[1].transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
fig.legend(handles=[Line2D([], [], marker="o", ls="-", color="black", mfc="black", ms=4.2, lw=1.0, label=f"all users (n = {meta['n_users']['default']:,} / {meta['n_users']['strict']:,})"),
                    Line2D([], [], marker="s", ls="-", color=OI["orange"], mfc=OI["orange"], ms=4.2, lw=1.0, label=f"non-cohort users (n = {meta['n_noncohort']['default']:,} / {meta['n_noncohort']['strict']:,})"),
                    Line2D([], [], marker="o", ls="", color=GREY, mfc="white", ms=4.2, label="open marker: Holm-adjusted p ≥ 0.05")],
           loc="lower center", ncol=3, bbox_to_anchor=(0.645, -0.005), columnspacing=1.4, handletextpad=0.3)
save(fig, "Fig2_paired_differences", "Paired bootstrap differences in Hit@10 (95% CI) between tuned models, all users and non-cohort users", "e7bstats_paired_ci.csv (variant mean_all_seeds, metric hit10)")
f_ = lambda r: f"{pp(r['diff'], 2)} [{pp(r.ci_lo, 2)}, {pp(r.ci_hi, 2)}]"
sl_d, sl_s = crow(SA, LN, "default", "all"), crow(SA, LN, "strict", "all"); sg_s = crow(SA, GR, "strict", "all")
ob = crow(T("SASRec"), "SASRec (E7)", "strict", "all")
tadef = [crow(a, b, "default", "all") for a, b in ((LA, LN), (GT, GR), (ST, SA))]; tastr = [crow(a, b, "strict", "all") for a, b in ((LA, LN), (GT, GR), (ST, SA))]
ncomp = len(c0[(c0.protocol == "default") & (c0["subset"] == "all")])
CAP["Fig2"] = (f"**Figure 2. After equal tuning the backbones are equivalent on the default protocol, SASRec leads on the strict protocol, and temporal attention adds no reliable gain.** Paired difference in Hit@10 "
    f"(first-named model minus second-named, percentage points) with 95% percentile bootstrap intervals (10,000 resamples of test users; per-user outcomes averaged over ten seeds). "
    f"All models are the budget-matched E7b models; the last block compares the E7b models with their E7 counterparts, which were selected on default-protocol validation Hit@10 only. "
    f"Filled markers: Holm-adjusted p < 0.05 within each protocol and user subset ({ncomp} comparisons in the family); open markers: not significant. The orange series removes the {meta['n_cohort']['default']:,} cohort users "
    f"({meta['n_cohort']['default'] / meta['n_users']['default']:.1%}) whose training history is the fixed curriculum 46→47→21. "
    f"Key contrasts, all users: SASRec minus LSTM {f_(sl_d)} (default) and {f_(sl_s)} (strict; Holm p = {sl_s.p_holm:.3f}); SASRec minus GRU4Rec {f_(sg_s)} (strict); "
    f"temporal attention, default: LSTM {pp(tadef[0]['diff'], 2)}, GRU4Rec {pp(tadef[1]['diff'], 2)}, SASRec {pp(tadef[2]['diff'], 2)}; strict: LSTM {pp(tastr[0]['diff'], 2)}, GRU4Rec {pp(tastr[1]['diff'], 2)}, "
    f"SASRec {pp(tastr[2]['diff'], 2)} (significant after Holm correction: {sum(bool(r.significant_holm_05) for r in tadef + tastr)} of 6); selection objective, SASRec strict {f_(ob)}.")

# =====================================================================================================================================
# Figure 3: cohort decomposition + seed-89 explanation
# =====================================================================================================================================
fig = plt.figure(figsize=(W2, 3.1))
gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.15], wspace=0.14, left=0.155, right=0.99, top=0.90, bottom=0.17)
a1, a2, a3 = [fig.add_subplot(gs[0, i]) for i in range(3)]
yp, yc = {}, 0
for g, ms in GROUPS:
    for m in ms: yp[m] = yc; yc += 1
    yc += 0.45
SUBS = (("cohort", OI["purple"], "D", "cohort users"), ("noncohort", OI["orange"], "o", "non-cohort users"), ("all", OI["black"], "|", "all users"))
for ax, pr in ((a1, "default"), (a2, "strict")):
    for m, y_ in yp.items():
        vs = {s: M(m, pr, s, "Hit@10") for s, *_ in SUBS}
        ax.plot([min(vs.values()), max(vs.values())], [y_, y_], color=LIGHT, lw=1.0, zorder=1)
        for s, col, mk, _ in SUBS:
            if s == "all": ax.scatter([vs[s]], [y_], s=24, marker="|", color=col, lw=1.0, zorder=3)
            else: ax.scatter([vs[s]], [y_], s=17 if mk == "D" else 19, marker=mk, color=col, lw=0, zorder=4)
    ax.set_ylim(yc - 0.9, -0.7); ax.set_xlim(-0.03, 1.03); ax.xaxis.grid(True, color=LIGHT, lw=0.5); ax.set_xlabel("Hit@10"); ax.set_title(f"{pr} protocol", fontsize=7, loc="left", pad=3)
a1.set_yticks(list(yp.values())); a1.set_yticklabels([LABEL[m] for m in yp]); a1.tick_params(axis="y", length=0); a2.set_yticks([]); a2.spines["left"].set_visible(False)
for ax, let in ((a1, "a"), (a2, "b"), (a3, "c")): ax.text(-0.02, 1.07, let, transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")
a1.legend(handles=[Line2D([], [], marker="D", ls="", color=OI["purple"], ms=4, label="cohort"), Line2D([], [], marker="o", ls="", color=OI["orange"], ms=4.4, label="non-cohort"),
                   Line2D([], [], marker="|", ls="", color="black", ms=6, label="all users")], loc="lower left", bbox_to_anchor=(0.0, 0.0), handletextpad=0.1, borderaxespad=0.1)
sf = ps[(ps.model == "SASRec+feat") & (ps.protocol == "strict")].set_index(["subset", "seed"])["Hit@10"]
xs = np.arange(len(SEEDS))
for sub, col, mk, lab in (("all", OI["black"], "o", "all users"), ("cohort", OI["purple"], "D", "cohort users"), ("noncohort", OI["orange"], "s", "non-cohort users")):
    a3.plot(xs, [sf[(sub, s)] for s in SEEDS], color=col, lw=0.9, marker=mk, ms=3.6, mfc=col, mec=col, label=lab, zorder=3)
i89 = SEEDS.index(89)
a3.annotate("seed 89", xy=(i89, sf[("cohort", 89)]), xytext=(i89 - 2.2, 0.28), fontsize=6.5, arrowprops=dict(arrowstyle="-", lw=0.6, color=GREY), ha="center", va="center")
a3.set_xticks(xs); a3.set_xticklabels([str(s) for s in SEEDS], rotation=60, fontsize=6); a3.set_ylim(-0.03, 1.05); a3.yaxis.grid(True, color=LIGHT, lw=0.5)
a3.set_xlabel("training seed"); a3.set_ylabel("Hit@10, strict protocol"); a3.yaxis.set_label_position("right"); a3.yaxis.tick_right(); a3.spines["right"].set_visible(True); a3.spines["left"].set_visible(False)
a3.set_title("SASRec + features (E4), per seed", fontsize=7, loc="left", pad=3); a3.legend(loc="lower left", bbox_to_anchor=(0.0, 0.0), handletextpad=0.2, borderaxespad=0.1)
save(fig, "Fig3_cohort", "Hit@10 for cohort vs non-cohort users under both protocols; per-seed strict Hit@10 of the SASRec + features model", "results_master.csv, p4_per_seed.csv")
other = [sf[("cohort", s)] for s in SEEDS if s != 89]
nonc = [M(m, "default", "noncohort", "Hit@10") for m in NEURAL]
CAP["Fig3"] = (f"**Figure 3. A fixed curriculum inflates every model's score; excluding it separates the models, and it explains the one seed that failed.** "
    f"The cohort is the {meta['n_cohort']['default']:,} of {meta['n_users']['default']:,} test users ({meta['n_cohort']['default'] / meta['n_users']['default']:.1%}) whose training history is exactly 46→47→21, the first three steps of the curriculum 46→47→21→52→60. "
    f"(a, b) Hit@10 for cohort users (diamonds), all other users (circles) and everybody (ticks) for the baselines and the six tuned neural models, under the default and strict protocols; the cohort is "
    f"{M(M_SA, 'default', 'cohort', 'Hit@10'):.3f} for SASRec under the default protocol, whereas non-cohort Hit@10 spans {min(nonc):.3f}–{max(nonc):.3f} across the neural models. "
    f"Under the strict protocol the Markov models score {M('Markov 1st', 'strict', 'cohort', 'Hit@10'):.4f} on the cohort because course 52, the validation target, is missing from their history. "
    f"(c) Strict-protocol Hit@10 of the SASRec + features model of E4 (not part of the tuned set) for each training seed. In seed 89 the cohort score falls to {sf[('cohort', 89)]:.4f} (other seeds {min(other):.4f}–{max(other):.4f}) "
    f"while non-cohort users are unchanged ({sf[('noncohort', 89)]:.4f}); the all-user mean therefore drops to {sf[('all', 89)]:.3f}. Course-only SASRec (E4) has cohort Hit@10 of at least "
    f"{ps[(ps.model == 'SASRec') & (ps.protocol == 'strict') & (ps['subset'] == 'cohort')]['Hit@10'].min():.4f} in every seed.")

# =====================================================================================================================================
# Figure 4: attention diagnostics (tuned models)
# =====================================================================================================================================
AM = [M_LA, M_GT, M_ST]
fig = plt.figure(figsize=(W2, 2.45))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.25], wspace=0.34, left=0.075, right=0.99, top=0.88, bottom=0.30)
b1, b2, b3 = [fig.add_subplot(gs[0, i]) for i in range(3)]
rng = np.random.default_rng(3)
for k, m in enumerate(AM):
    d = att[att.model == m]; assert len(d) == len(SEEDS), m
    for ax, col in ((b1, "entropy_ratio"), (b2, "last_over_uniform")):
        ax.scatter(k + rng.uniform(-0.12, 0.12, len(d)), d[col], s=7, color=MCOL[m], alpha=0.8, lw=0, zorder=3)
        ax.plot([k - 0.26, k + 0.26], [d[col].mean()] * 2, color="black", lw=1.0, zorder=4)
ylo1 = min(0.80, np.floor(att[att.model.isin(AM)].entropy_ratio.min() * 20) / 20)
yr2 = (min(0.7, att[att.model.isin(AM)].last_over_uniform.min() - 0.05), max(1.4, att[att.model.isin(AM)].last_over_uniform.max() + 0.05))
for ax, ylab_, let, yl in ((b1, "Normalised attention entropy", "a", (ylo1, 1.02)), (b2, "Weight on latest course / uniform weight", "b", yr2)):
    ax.axhline(1.0, color=GREY, lw=0.7, ls=(0, (3, 2)), zorder=1); ax.set_ylim(*yl); ax.set_xlim(-0.6, len(AM) - 0.4)
    ax.set_xticks(range(len(AM))); ax.set_xticklabels(["LSTM\n+ attention", "GRU4Rec\n+ TA", "SASRec\n+ TA"], fontsize=6.3); ax.tick_params(axis="x", length=0)
    ax.set_ylabel(ylab_); ax.yaxis.grid(True, color=LIGHT, lw=0.5); ax.text(0.0, 1.04, let, transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")
b1.text(len(AM) - 0.45, 1.003, "uniform", ha="right", va="bottom", fontsize=6, color=GREY); b2.text(len(AM) - 0.45, 1.01, "uniform", ha="right", va="bottom", fontsize=6, color=GREY)
cnt = attl[attl.model.isin(AM)].groupby(["model", "history_len"]).n_users.sum().reset_index(); keepn = sorted(set(cnt[cnt.n_users >= 10 * 30].history_len))
for m in AM:
    d = attl[(attl.model == m) & (attl.history_len.isin(keepn))].groupby("history_len")[["last_pos_weight", "uniform_weight"]].mean()
    b3.plot(d.index, d.last_pos_weight, color=MCOL[m], marker="o", ms=3, lw=1.0, label=LABEL[m])
d = attl[(attl.model == AM[0]) & (attl.history_len.isin(keepn))].groupby("history_len").uniform_weight.mean()
b3.plot(d.index, d.values, color="black", ls=(0, (3, 2)), lw=0.9, label="uniform (1 / history length)")
b3.set_xlabel("History length (courses)"); b3.set_ylabel("Weight on latest course"); b3.set_xticks(keepn); b3.yaxis.grid(True, color=LIGHT, lw=0.5)
b3.legend(loc="upper right", labelspacing=0.2, handlelength=1.7); b3.text(0.0, 1.04, "c", transform=b3.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")
save(fig, "Fig4_attention_diagnostics", "Attention-weight diagnostics of the three tuned attention models (default protocol, all test users with history >= 2)", "p4_attention_diag.csv, p4_attention_by_len.csv")
ae = att[att.model.isin(AM)].groupby("model").mean(numeric_only=True)
CAP["Fig4"] = (f"**Figure 4. The learned attention is diffuse and shows little preference for the most recent course.** Diagnostics of the learned attention over the user's course history for the three tuned models that use it, "
    f"computed on the test users with at least two prior courses (default protocol). "
    f"(a) Entropy of the attention distribution divided by the entropy of a uniform distribution (1 = uniform), one dot per seed, bar = mean over seeds: " + ", ".join(f"{LABEL[m]} {ae.loc[m, 'entropy_ratio']:.2f}" for m in AM) + ". "
    f"(b) Weight on the most recent course divided by the uniform weight 1/n: " + ", ".join(f"{LABEL[m]} {ae.loc[m, 'last_over_uniform']:.2f}" for m in AM) + ". "
    f"(c) Mean weight on the most recent course by history length against the uniform weight; history lengths with fewer than 30 users per seed are omitted.")

# =====================================================================================================================================
# Figure S1: forward-time audit
# =====================================================================================================================================
TAL = {"S0_base": "SASRec\n(base)", "T_gap": "+ time\ngaps", "C_calendar": "+ calendar\nmonth", "P_candprior": "+ candidate\nprior", "TCP": "+ all\nthree", "Q_trend": "+ trend\ncounts", "Q4_trend_trans": "+ trend +\ntransitions"}
vs = [v for v in TAL if v in set(ta.variant)]
fig, ax = plt.subplots(figsize=(W2 * 0.62, 2.55)); fig.subplots_adjust(left=0.115, right=0.99, top=0.95, bottom=0.27)
rng = np.random.default_rng(5)
for i, v in enumerate(vs):
    d = ta[ta.variant == v]["future_Hit@10"].values
    ax.scatter(i + rng.uniform(-0.11, 0.11, len(d)), d, s=9, color=OI["blue"] if v == "S0_base" else OI["sky"], lw=0, alpha=0.9, zorder=3)
    ax.plot([i - 0.25, i + 0.25], [d.mean()] * 2, color="black", lw=1.0, zorder=4)
ax.set_xticks(range(len(vs))); ax.set_xticklabels([TAL[v] for v in vs], fontsize=6); ax.tick_params(axis="x", length=0)
ax.set_ylabel("Hit@10 on later-dated users"); ax.yaxis.grid(True, color=LIGHT, lw=0.5)
ax.axhline(ta[ta.variant == "S0_base"]["future_Hit@10"].mean(), color=GREY, lw=0.6, ls=(0, (3, 2)), zorder=1)
save(fig, "FigS1_forward_time_audit", "Forward-in-time audit: SASRec with time-aware inputs, trained before 2025-10-01 and evaluated after", "x1_timeaudit_val.csv")
g = ta.groupby("variant")["future_Hit@10"].agg(["mean", "std", "count"])
bs = ta[ta.variant == "S0_base"].set_index("seed")["future_Hit@10"]
dd = {v: (ta[ta.variant == v].set_index("seed")["future_Hit@10"] - bs).dropna() for v in TAL if v != "S0_base" and v in set(ta.variant)}
CAP["FigS1"] = (f"**Figure S1. Forward-in-time audit: absolute Hit@10 is about {g.loc['S0_base', 'mean']:.2f}, and only the trend-count inputs help.** SASRec trained only on course sequences whose target date is before 2025-10-01, early-stopped on earlier-dated validation users and "
    f"evaluated on the {int(ta.n_future_eval.iloc[0]):,} validation users whose target date is on or after 2025-10-01 ({int(ta.n_train.iloc[0]):,} training prefixes). Dots are single seeds (3–5 per variant; seeds 7, 13, 42, 101, 202), bars are means, the dashed line is the base model "
    f"({g.loc['S0_base', 'mean']:.4f}, SD {g.loc['S0_base', 'std']:.4f}). Mean paired gain over base: " + ", ".join(f"{v} {pp(d.mean(), 1)} pp" for v, d in dd.items()) +
    ". Calendar month and time gaps do not separate from base; inputs built from past platform enrolment counts (candidate prior, trend counts, transitions) give +1.5 to +2.0 pp. "
    "This audit used validation users, not test users, and did not assess stability under the strict protocol or on the test set. Variant definitions are in Table S7.")

# =====================================================================================================================================
# Figure S2: seed-level Hit@10 (E7b)
# =====================================================================================================================================
fig, axs = plt.subplots(1, 2, figsize=(W2, 2.6), sharey=True); fig.subplots_adjust(left=0.19, right=0.99, top=0.93, bottom=0.16, wspace=0.07)
for ax, pr, let in zip(axs, ("default", "strict"), "ab"):
    for i, m in enumerate(NEURAL):
        v = ps[(ps.model == m) & (ps.protocol == pr) & (ps["subset"] == "all")].sort_values("seed")["Hit@10"].values
        ax.scatter(v, i + rng.uniform(-0.15, 0.15, len(v)), s=7, color=MCOL[m], alpha=0.8, lw=0, zorder=3)
        ax.plot([v.mean()] * 2, [i - 0.3, i + 0.3], color="black", lw=1.0, zorder=4)
    ax.set_ylim(len(NEURAL) - 0.4, -0.7); ax.xaxis.grid(True, color=LIGHT, lw=0.5); ax.set_xlabel(f"Hit@10, {pr} protocol")
    ax.text(0.0, 1.02, let, transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")
axs[0].set_yticks(range(len(NEURAL))); axs[0].set_yticklabels([LABEL[m] for m in NEURAL]); axs[0].tick_params(axis="y", length=0); axs[1].spines["left"].set_visible(False)
save(fig, "FigS2_seed_level_hit10", "Hit@10 per training seed for the six tuned neural models (E7b), both protocols", "p4_per_seed.csv")
sd_all = {m: M(m, "default", "all", "Hit@10", "sd") for m in NEURAL}
CAP["FigS2"] = (f"**Figure S2. Seed-to-seed spread is of the same order as most model differences.** Hit@10 of each tuned neural model (E7b) for each of the ten training seeds (dots) and the mean (bar), under the default (a) "
    f"and strict (b) protocols. Seed standard deviation, default protocol: {min(sd_all.values()) * 100:.2f} to {max(sd_all.values()) * 100:.2f} percentage points.")

# =====================================================================================================================================
# Figure S3: effect of the tuning protocol (E3-E5 vs E7 vs E7b)
# =====================================================================================================================================
LEG = {M_LN: "LSTM no attn (B)", M_LA: "LSTM+attn (A, paper)", M_GR: "GRU4Rec", M_GT: "GRU4Rec+TA", M_SA: "SASRec", M_ST: "SASRec+TA"}
SETS = (("E3–E5 (small grid)", lambda m: LEG[m], "o", "white", OI["black"]), ("E7 (validation Hit@10)", lambda m: m.replace("[E7B]", "[E7]"), "s", OI["blue"], OI["blue"]),
        ("E7b (default + strict validation)", lambda m: m, "D", OI["verm"], OI["verm"]))
fig, axs = plt.subplots(1, 2, figsize=(W2, 2.9), sharey=True); fig.subplots_adjust(left=0.19, right=0.99, top=0.88, bottom=0.17, wspace=0.07)
for ax, pr, let in zip(axs, ("default", "strict"), "ab"):
    for i, m in enumerate(NEURAL):
        for k, (lab, fn, mk, fc, ec) in enumerate(SETS):
            nm = fn(m); mu, sd = M(nm, pr, "all", "Hit@10"), M(nm, pr, "all", "Hit@10", "sd"); yy_ = i + (k - 1) * 0.22
            ax.plot([mu - sd, mu + sd], [yy_, yy_], color=ec, lw=0.8, zorder=2); ax.scatter([mu], [yy_], s=14, marker=mk, facecolor=fc, edgecolor=ec, lw=0.9, zorder=3)
    ax.set_ylim(len(NEURAL) - 0.4, -0.7); ax.xaxis.grid(True, color=LIGHT, lw=0.5); ax.set_xlabel(f"Hit@10, {pr} protocol (mean ± seed SD)")
    ax.text(0.0, 1.02, let, transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")
axs[0].set_yticks(range(len(NEURAL))); axs[0].set_yticklabels([LABEL[m] for m in NEURAL]); axs[0].tick_params(axis="y", length=0); axs[1].spines["left"].set_visible(False)
fig.legend(handles=[Line2D([], [], marker=mk, ls="-", lw=0.8, color=ec, mfc=fc, ms=4, label=lab) for lab, fn, mk, fc, ec in SETS], loc="upper center", ncol=3, bbox_to_anchor=(0.6, 1.0), columnspacing=1.6, handletextpad=0.4)
save(fig, "FigS3_tuning_protocol", "Hit@10 of the six models under three tuning protocols (E3-E5, E7, E7b), both test protocols", "results_master.csv")
CAP["FigS3"] = (f"**Figure S3. The ranking of the models depends on how they were tuned.** Test Hit@10 (mean ± SD over ten seeds) of the same six model families after three tuning protocols: the small validation grid of E3–E5 "
    f"(open circles), 30 Optuna trials per model selected on default-protocol validation Hit@10 (E7, squares), and the same search selected on the mean of default and strict validation Hit@10 (E7b, diamonds). "
    f"SASRec strict Hit@10 is {M('SASRec', 'strict', 'all', 'Hit@10'):.4f} (E3–E5), {M('SASRec [E7]', 'strict', 'all', 'Hit@10'):.4f} (E7) and {M(M_SA, 'strict', 'all', 'Hit@10'):.4f} (E7b); "
    f"LSTM + attention default Hit@10 is {M('LSTM+attn (A, paper)', 'default', 'all', 'Hit@10'):.4f}, {M('LSTM+attn (paper) [E7]', 'default', 'all', 'Hit@10'):.4f} and {M(M_LA, 'default', 'all', 'Hit@10'):.4f}.")

(OUT / "figure_captions.md").write_text("# Figure captions (values generated from results_master.csv, e7bstats_paired_ci.csv, p4_attention_*.csv, x1_timeaudit_val.csv)\n\n"
                                      + "\n\n".join(CAP[k] for k in ("Fig1", "Fig2", "Fig3", "Fig4", "FigS1", "FigS2", "FigS3")) + "\n")
pd.DataFrame(MANIFEST).to_csv(OUT / "figure_manifest.csv", index=False)
print("captions written:", OUT / "figure_captions.md")
