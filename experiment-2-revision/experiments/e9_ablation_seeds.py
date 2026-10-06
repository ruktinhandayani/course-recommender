"""E9 - repeated-seed paired CIs for the original Table 5 metadata-feature ablation (reviewer comment 5).
A1 Course history only | A2 +Competency | A3 +Level | A4 +Certificate flag | A5 Full model (+ cert frequency).
Same architecture/recipe as the published model (common.models.build_lstm_attention); only which per-step
embeddings are concatenated before the encoder LSTM changes. All 5 Input layers are always declared (so
D.X_train/X_val/X_test can be passed unchanged for every config) -- unused inputs for A1-A4 are simply not
wired into the computation graph. H1-H3 (hyperparameter sensitivity) is NOT redone here: it is superseded by
the much larger budget-matched Optuna search in E7/E7b, which already covers this ground across 10 seeds.

For every (config, seed): train, evaluate default + strict with full-history masking, save per-user arrays.
Finished runs are skipped on resume. After training, STEP 4 computes paired bootstrap CIs of each A1-A4 vs
A5 (the full model), Holm-corrected within protocol x metric, reusing the E6 bootstrap method.

Run:   python experiment-2-revision/experiments/e9_ablation_seeds.py                  (5 configs x 5 seeds, ~25 min)
       python experiment-2-revision/experiments/e9_ablation_seeds.py --configs A1 A5 --seeds 42   (quick test)
Watch: tail -f experiment-2-revision/logs/e9_ablation_*.log
"""
import argparse, os, sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser()
ap.add_argument("--configs", nargs="+", default=["A1", "A2", "A3", "A4", "A5"], choices=["A1", "A2", "A3", "A4", "A5"])
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202, 7, 13])
ap.add_argument("--epochs", type=int, default=50); ap.add_argument("--batch-size", type=int, default=64)
ap.add_argument("--patience", type=int, default=5); ap.add_argument("--tag", default="e9")
ap.add_argument("--boot", type=int, default=10000)
args = ap.parse_args()
from common.provenance import start_run, say, save_json, ROOT, order_digest
log, meta = start_run(f"{args.tag}_ablation", args)

import numpy as np, pandas as pd, keras
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.models import TemporalAttention
from common.metrics import evaluate_scores

say("STEP 1  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)

FEATURES = {"A1": (), "A2": ("comp",), "A3": ("comp", "level"), "A4": ("comp", "level", "flag"), "A5": ("comp", "level", "flag", "cnt")}
NAME = {"A1": "A1_course_only", "A2": "A2_plus_competency", "A3": "A3_plus_level", "A4": "A4_plus_certflag", "A5": "A5_full_model"}


def build_lstm_ablation(D, feature_set, seed=42, cfg=None):
    """Same architecture/recipe as common.models.build_lstm_attention; feature_set in FEATURES controls which
    embeddings are concatenated before the encoder (A1-A4 subsets of the full A5 feature set)."""
    cfg = {"course_dim": 96, "comp_dim": 32, "level_dim": 8, "latent": 192, "dropout": 0.3, "lr": 1e-3, **(cfg or {})}
    L = D.X_train[0].shape[1]; L_ = keras.layers
    i_course = L_.Input((L,), name="course_input")
    i_comp = L_.Input((L,), name="competency_input")
    i_level = L_.Input((L,), name="level_input")
    i_flag = L_.Input((L, 1), name="course_has_certificate_input")
    i_cnt = L_.Input((L, 1), name="certificate_count_input")
    use = FEATURES[feature_set]
    parts = [L_.Embedding(D.num_courses, cfg["course_dim"], name="course_embedding")(i_course)]
    if "comp" in use:
        parts.append(L_.Embedding(D.num_competencies, cfg["comp_dim"], name="competency_embedding")(i_comp))
    if "level" in use:
        parts.append(L_.Embedding(D.num_levels, cfg["level_dim"], name="level_embedding")(i_level))
    if "flag" in use:
        parts.append(i_flag)
    if "cnt" in use:
        parts.append(i_cnt)
    x = L_.Concatenate(name="combined_encoder_input")(parts) if len(parts) > 1 else parts[0]
    seq, h, c = L_.LSTM(cfg["latent"], return_sequences=True, return_state=True, name="encoder_lstm")(x)
    ctx, _ = TemporalAttention(name="temporal_attention")([seq, i_course])
    st_in = L_.Concatenate(name="attention_state_concatenate")([h, ctx])
    st = L_.Dense(cfg["latent"], activation="tanh", name="attention_enhanced_state")(st_in)
    dec = L_.LSTM(cfg["latent"], name="decoder_lstm")(L_.RepeatVector(1, name="decoder_repeat")(st), initial_state=[st, c])
    out = L_.Dense(D.num_courses, activation="softmax", name="course_prediction")(
        L_.Dropout(cfg["dropout"], name="decoder_representation")(dec))
    model = keras.Model([i_course, i_comp, i_level, i_flag, i_cnt], out)   # 5 inputs ALWAYS, even if some are unused
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=cfg["lr"]), loss="sparse_categorical_crossentropy")
    return model


out = ROOT / "results"; pdir = out / f"{args.tag}_peruser"; pdir.mkdir(exist_ok=True)
runs = [(cfg, s) for s in args.seeds for cfg in args.configs]
say(f"STEP 2  {len(runs)} runs: configs {args.configs} x seeds {args.seeds}")
csv = out / f"{args.tag}_ablation.csv"
rows = pd.read_csv(csv).to_dict("records") if csv.exists() else []
t_all = time.time(); done_now = 0

for k, (cfg, seed) in enumerate(runs, 1):
    f = pdir / f"{NAME[cfg]}_seed{seed}.npz"
    if f.exists():
        say(f"[{k}/{len(runs)}] {NAME[cfg]} seed {seed}: already done, skipping"); continue
    say(f"[{k}/{len(runs)}] {NAME[cfg]} seed {seed}: training")
    keras.utils.set_random_seed(seed)
    model = build_lstm_ablation(D, cfg, seed=seed)

    class Mon(keras.callbacks.Callback):
        def on_epoch_end(self, e, logs=None):
            say(f"    epoch {e+1:02d}  loss={logs['loss']:.4f}  val_loss={logs['val_loss']:.4f}")

    h = model.fit(D.X_train, D.y_train, validation_data=(D.X_val, D.y_val), epochs=args.epochs, batch_size=args.batch_size,
                  shuffle=True, verbose=0, callbacks=[Mon(),
                  keras.callbacks.EarlyStopping(monitor="val_loss", mode="min", patience=args.patience, restore_best_weights=True),
                  keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)])
    arrays = {}
    for nm, (X, y, mt) in D.splits.items():
        r, pu, top = evaluate_scores(model.predict(X, batch_size=512, verbose=0), D.seen[nm], y, D.num_courses)
        rows.append({"config": NAME[cfg], "seed": seed, "protocol": nm, "params": model.count_params(),
                     "epochs_run": len(h.history["loss"]), "best_val_loss": min(h.history["val_loss"]),
                     **{kk: float(vv) for kk, vv in r.items()}})
        for kk, vv in pu.items():
            arrays[f"{nm}_{kk}"] = vv
        arrays[f"{nm}_top10"] = top; arrays[f"{nm}_y"] = y
        arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
        say(f"    {nm:8s} " + "  ".join(f"{kk}={float(vv):.4f}" for kk, vv in r.items() if kk != "Coverage@10"))
    np.savez_compressed(f, **arrays); pd.DataFrame(rows).to_csv(csv, index=False)
    done_now += 1; el = time.time() - t_all; left = (len(runs) - k) * el / max(done_now, 1)
    say(f"    saved {f.name}; elapsed {el/60:.1f} min, estimated remaining {left/60:.1f} min")
    del model; keras.backend.clear_session()

df = pd.read_csv(csv)
mc = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10"]
agg = df.groupby(["config", "protocol"])[mc].agg(["mean", "std"]).round(4)
agg["n_seeds"] = df.groupby(["config", "protocol"]).size()
agg.to_csv(out / f"{args.tag}_ablation_summary.csv")
say("SUMMARY (mean / std over seeds)"); print(agg.to_string())

# ---- STEP 4: paired bootstrap CI of each A1-A4 vs A5, Holm-corrected (same method as E6) ------------------
say("STEP 4  paired bootstrap CI: each config vs A5 (full model)")
metas = {"default": D.meta_test, "strict": D.meta_test_strict}
digest = {pr: order_digest(m.user_id) for pr, m in metas.items()}
per = {cfg: {pr: {} for pr in metas} for cfg in args.configs}
for cfg in args.configs:
    for seed in args.seeds:
        z = np.load(pdir / f"{NAME[cfg]}_seed{seed}.npz")
        for pr in metas:
            assert str(z[f"{pr}_order_sha256"]) == digest[pr], f"user order mismatch {NAME[cfg]} seed {seed} {pr}"
            per[cfg][pr][seed] = {"hit10": z[f"{pr}_hit10"], "rr10": z[f"{pr}_rr10"]}
rng = np.random.default_rng(0)


def avg(cfg, pr, metric):
    d = per[cfg][pr]
    return np.mean([d[s][metric] for s in d], axis=0)


def boot_means(Dm, B):
    n = Dm.shape[0]; out = np.empty((B, Dm.shape[1]), np.float64); i = 0
    while i < B:
        b = min(500, B - i); idx = rng.integers(0, n, (b, n))
        W = np.zeros((b, n), np.float32)
        for r in range(b):
            W[r] = np.bincount(idx[r], minlength=n)
        out[i:i + b] = (W @ Dm.astype(np.float32)) / n; i += b
    return out


def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for rank, j in enumerate(o):
        run = max(run, (m - rank) * p[j]); adj[j] = min(1.0, run)
    return adj


if "A5" in args.configs and len(args.configs) > 1:
    res = []
    for pr in metas:
        cols, labels = [], []
        for cfg in args.configs:
            if cfg == "A5":
                continue
            for metric in ("hit10", "rr10"):
                cols.append(avg(cfg, pr, metric) - avg("A5", pr, metric)); labels.append((cfg, metric))
        Dm = np.stack(cols, 1); bm = boot_means(Dm, args.boot); pt = Dm.mean(0)
        lo, hi = np.percentile(bm, 2.5, 0), np.percentile(bm, 97.5, 0)
        p = 2 * np.minimum((bm <= 0).mean(0), (bm >= 0).mean(0)); p = np.maximum(p, 1.0 / args.boot)
        for (cfg, metric), d, l, h, pv in zip(labels, pt, lo, hi, p):
            res.append({"protocol": pr, "a": cfg, "b": "A5", "metric": metric, "n_seeds": len(args.seeds),
                        "diff": d, "ci_lo": l, "ci_hi": h, "p_boot": pv})
    res = pd.DataFrame(res); res["p_holm"] = np.nan
    for pr, idx in res.groupby("protocol").groups.items():
        res.loc[idx, "p_holm"] = holm(res.loc[idx, "p_boot"].values)
    res["significant_holm_05"] = res["p_holm"] < 0.05
    res["ci_excludes_0"] = (res.ci_lo > 0) | (res.ci_hi < 0)
    res.to_csv(out / f"{args.tag}_paired_ci.csv", index=False)
    say("  (a - A5), Hit@10 and MRR@10, Holm-corrected within protocol (* = CI excludes 0, H = significant after Holm)")
    for _, r in res[res.metric == "hit10"].iterrows():
        flag = ("*" if r.ci_excludes_0 else " ") + ("H" if r.significant_holm_05 else " ")
        say(f"  {flag} {r.protocol:8s} {r.a} - A5  {r['diff']:+.4f}  [{r.ci_lo:+.4f}, {r.ci_hi:+.4f}]  p_holm={r.p_holm:.4f}")
else:
    say("  skipped (need A5 plus at least one other config in --configs)")

save_json({"meta": meta, "configs": args.configs, "seeds": args.seeds, "boot": args.boot}, out / f"{args.tag}_ablation_meta.json")
say(f"{args.tag.upper()} DONE -> results/{args.tag}_ablation*.csv, results/{args.tag}_paired_ci.csv")
