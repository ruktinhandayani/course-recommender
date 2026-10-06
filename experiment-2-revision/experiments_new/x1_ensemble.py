"""x1_ensemble - VALIDATION-ONLY test of score-level hybrids: SASRec + LSTM-attention (+ time-aware X-SASRec) + Markov prior.
Trains N seeds of each member family, stores validation probabilities (results/x1_ensemble_valprobs/), then compares
  * same-family seed ensembles (variance reduction only)   vs   * mixed-family ensembles of the SAME size (architecture diversity)
  * a fixed Markov-prior mixture (1-lam)*p_neural + lam*p_markov.
Run: python experiment-2-revision/experiments_new/x1_ensemble.py [--seeds 42 101 202 7 13] [--quick]"""
import argparse, os, sys, warnings, itertools
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2"); os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202, 7, 13])
ap.add_argument("--xvariant", default="TCP", help="X-SASRec variant used as third family")
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
from common.provenance import start_run, say, ROOT
TAG = "x1quick_ensemble" if args.quick else "x1_ensemble"
log, meta = start_run(TAG, args)
import numpy as np, pandas as pd, keras, xlib
from common.metrics import evaluate_scores
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.models import build_sasrec, build_lstm_attention
from common import baselines
D = build_dataset(); assert_contract(D, raw=True)
FE = xlib.attach(D, xlib.build_features(D))
pdir = ROOT / "results" / f"{TAG}_valprobs"; pdir.mkdir(exist_ok=True)
seeds = [42] if args.quick else args.seeds
EP = 2 if args.quick else 50

def fitkeras(m, Xtr, Xva):
    mon = "val_loss"
    return m.fit(Xtr, D.y_train, validation_data=(Xva, D.y_val), epochs=EP, batch_size=64, shuffle=True, verbose=0,
                 callbacks=[keras.callbacks.EarlyStopping(monitor=mon, patience=5, restore_best_weights=True),
                            keras.callbacks.ReduceLROnPlateau(monitor=mon, mode="min", factor=0.5, patience=2, min_lr=1e-5)])
for seed in seeds:
    for fam in ("sas", "lstm", "xsas"):
        f = pdir / f"{fam}_seed{seed}.npy"
        if f.exists(): say(f"{fam} seed {seed}: done"); continue
        keras.utils.set_random_seed(seed)
        if fam == "sas":
            m = build_sasrec(D, "course_only", {"d": 96, "blocks": 2, "heads": 2, "dropout": 0.2}); fitkeras(m, D.X_train[:1], D.X_val[:1]); p = m.predict(D.X_val[:1], batch_size=512, verbose=0)
        elif fam == "lstm":
            m = build_lstm_attention(D, seed=seed, attention="custom"); fitkeras(m, D.X_train, D.X_val); p = m.predict(D.X_val, batch_size=512, verbose=0)
        else:
            cfg = dict(xlib.VARIANTS[args.xvariant]); cfg.pop("augment_p", None)
            m = xlib.build_model(D, cfg); fitkeras(m, xlib.inputs_of(FE["train"]), xlib.inputs_of(FE["val"])); p = m.predict(xlib.inputs_of(FE["val"]), batch_size=512, verbose=0)
        p = (p[0] if isinstance(p, list) else p).astype("float32"); np.save(f, p)
        r, _, _ = evaluate_scores(p, D.seen_val, D.y_val, D.num_courses)
        say(f"{fam} seed {seed}: val Hit@10={r['Hit@10']:.4f} MRR@10={r['MRR@10']:.4f}"); keras.backend.clear_session()

# ------------------------------------------------------------------ analysis (validation only)
P = {fam: [np.load(pdir / f"{fam}_seed{s}.npy") for s in seeds] for fam in ("sas", "lstm", "xsas")}
C1, _, _ = baselines.transition_counts(D); pop = baselines.popularity(D)
Pm, _ = baselines.score_markov(D, D.X_val, C1, pop); Pm = Pm / Pm.sum(1, keepdims=True)
H = lambda p: evaluate_scores(p, D.seen_val, D.y_val, D.num_courses)[0]
rows = []
def add(name, p):
    r = H(p); rows.append({"ensemble": name, "Hit@10": r["Hit@10"], "Hit@1": r["Hit@1"], "MRR@10": r["MRR@10"], "NDCG@10": r["NDCG@10"]}); say(f"  {name:48s} Hit@10={r['Hit@10']:.4f} Hit@1={r['Hit@1']:.4f} MRR@10={r['MRR@10']:.4f}")
n = len(seeds); say(f"VALIDATION ensembles (n seeds per family = {n})")
for fam in P:
    for i, s in enumerate(seeds): add(f"single {fam} seed {s}", P[fam][i])
    add(f"{fam} x{n} (seed ensemble, mean prob)", np.mean(P[fam], 0))
if n >= 3:
    k = min(n, 3)
    add(f"sas x{k}", np.mean(P["sas"][:k], 0))
    add(f"sas+lstm+xsas (1 each, seed {seeds[0]})", np.mean([P[f][0] for f in P], 0))
    add(f"sas x{k} + lstm x{k} (mixed, {2*k} members)", np.mean(P["sas"][:k] + P["lstm"][:k], 0))
    add(f"sas x{2*k} (same size, seeds only)" if 2 * k <= n else f"sas x{n} (seeds only)", np.mean(P["sas"][:2 * k], 0))
    add(f"sas+lstm+xsas x{k} (mixed, {3*k} members)", np.mean(P["sas"][:k] + P["lstm"][:k] + P["xsas"][:k], 0))
add(f"sas+lstm x{n} (mixed, {2*n} members)", np.mean(P["sas"] + P["lstm"], 0))
add(f"sas+lstm+xsas x{n} (mixed, {3*n} members)", np.mean(P["sas"] + P["lstm"] + P["xsas"], 0))
base = np.mean(P["sas"] + P["lstm"], 0)
for lam in (0.02, 0.05, 0.1, 0.2, 0.3):
    add(f"(sas+lstm x{n}) + Markov prior lam={lam}", (1 - lam) * base + lam * Pm)
pd.DataFrame(rows).to_csv(ROOT / "results" / f"{TAG}_val_summary.csv", index=False); say(f"{TAG} DONE")
