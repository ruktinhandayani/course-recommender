"""Shared harness for neural baselines (E3 GRU4Rec-style, E4 SASRec): tune on VALIDATION with one seed, then train the
chosen configuration for every seed, evaluate default+strict with full-history masking, save per-user arrays.
Same training recipe as the LSTM: Adam 1e-3, batch 64, <=50 epochs, EarlyStopping(val_loss, patience 5), LR halving.
Resumable: finished runs are skipped when you start it again."""
import itertools, json, time
import numpy as np, pandas as pd, keras
from .metrics import evaluate_scores
from .provenance import say, ROOT, order_digest, save_json


def select(setting, X):
    return X[:1] if setting == "course_only" else X


def fit(model, D, setting, args, tag):
    class Mon(keras.callbacks.Callback):
        def on_epoch_end(self, e, logs=None):
            say(f"      {tag} epoch {e+1:02d}  loss={logs['loss']:.4f}  val_loss={logs['val_loss']:.4f}")
    return model.fit(select(setting, D.X_train), D.y_train, validation_data=(select(setting, D.X_val), D.y_val),
                     epochs=args.epochs, batch_size=args.batch_size, shuffle=True, verbose=0,
                     callbacks=[Mon(), keras.callbacks.EarlyStopping(monitor="val_loss", mode="min", patience=args.patience, restore_best_weights=True),
                                keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)])


def run_experiment(name, tag, build, grid, D, args):
    settings = ["course_only", "full_features"]
    out = ROOT / "results"; pdir = out / f"{tag}_peruser"; pdir.mkdir(exist_ok=True)
    keys = list(grid); cfgs = [dict(zip(keys, v)) for v in itertools.product(*grid.values())]
    if args.quick:
        cfgs = cfgs[:1]
    # ---- 1. tuning on validation only (test never touched) -------------------------------------------------
    tfile = out / f"{tag}_tuning.json"
    tuning = json.loads(tfile.read_text()) if (tfile.exists() and not args.retune) else {}
    say(f"STEP 2  tuning on validation (seed {args.tune_seed}): {len(cfgs)} configs x {len(settings)} settings")
    for s in settings:
        tuning.setdefault(s, [])
        for c in cfgs:
            if any(t["cfg"] == c for t in tuning[s]):
                continue
            say(f"  tuning {name} [{s}] {c}")
            keras.utils.set_random_seed(args.tune_seed)
            m = build(D, s, c); h = fit(m, D, s, args, "tune")
            r, _, _ = evaluate_scores(m.predict(select(s, D.X_val), batch_size=512, verbose=0), D.seen_val, D.y_val, D.num_courses)
            tuning[s].append({"cfg": c, "val_Hit@10": float(r["Hit@10"]), "val_MRR@10": float(r["MRR@10"]),
                              "val_loss": float(min(h.history["val_loss"])), "epochs": len(h.history["loss"]), "params": m.count_params()})
            say(f"    -> val Hit@10={r['Hit@10']:.4f}  MRR@10={r['MRR@10']:.4f}  params={m.count_params()}")
            tfile.write_text(json.dumps(tuning, indent=2)); keras.backend.clear_session()
    best = {s: max([t for t in tuning[s] if t["cfg"] in cfgs], key=lambda t: (t["val_Hit@10"], t["val_MRR@10"]))["cfg"] for s in settings}
    for s in settings:
        say(f"  chosen [{s}]: {best[s]}")
    # ---- 2. final runs over seeds ---------------------------------------------------------------------------
    runs = [(s, seed) for seed in args.seeds for s in settings]
    say(f"STEP 3  {len(runs)} final runs: seeds {args.seeds} x settings {settings}")
    csv = out / f"{tag}.csv"; rows = pd.read_csv(csv).to_dict("records") if csv.exists() else []
    t0, ran = time.time(), 0
    for k, (s, seed) in enumerate(runs, 1):
        f = pdir / f"{name}_{s}_seed{seed}.npz"
        if f.exists():
            say(f"[{k}/{len(runs)}] {name}_{s} seed {seed}: already done, skipping"); continue
        say(f"[{k}/{len(runs)}] {name}_{s} seed {seed}: training {best[s]}")
        keras.utils.set_random_seed(seed)
        m = build(D, s, best[s]); h = fit(m, D, s, args, "run"); arrays = {}
        for nm, (X, y, mt) in D.splits.items():
            r, pu, top = evaluate_scores(m.predict(select(s, X), batch_size=512, verbose=0), D.seen[nm], y, D.num_courses)
            rows.append({"model": f"{name}_{s}", "seed": seed, "protocol": nm, "cfg": json.dumps(best[s]), "params": m.count_params(),
                         "epochs_run": len(h.history["loss"]), "best_val_loss": min(h.history["val_loss"]), **{kk: float(vv) for kk, vv in r.items()}})
            for kk, vv in pu.items():
                arrays[f"{nm}_{kk}"] = vv
            arrays[f"{nm}_top10"], arrays[f"{nm}_y"] = top, y; arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
            say(f"    {nm:8s} " + "  ".join(f"{kk}={float(vv):.4f}" for kk, vv in r.items() if kk != "Coverage@10"))
        if any(l.name == "temporal_attention" for l in m.layers):       # how selective is the learned attention?
            X = select(s, D.X_test); awm = keras.Model(m.inputs, m.get_layer("temporal_attention").output[1])
            w = awm.predict(X, batch_size=512, verbose=0); n = (D.X_test[0] != 0).sum(1)
            arrays["att_entropy_ratio"] = (-(np.where(w > 0, w * np.log(np.maximum(w, 1e-12)), 0)).sum(1)) / np.log(np.maximum(n, 2))
            arrays["att_max_weight"], arrays["att_uniform_weight"], arrays["att_last_pos_weight"] = w.max(1), 1.0 / np.maximum(n, 1), w[:, -1]
            say(f"    attention: entropy ratio={arrays['att_entropy_ratio'].mean():.3f} (1=uniform), max weight={arrays['att_max_weight'].mean():.3f} "
                f"vs uniform {arrays['att_uniform_weight'].mean():.3f}, weight on most recent course={arrays['att_last_pos_weight'].mean():.3f}")
        np.savez_compressed(f, **arrays); pd.DataFrame(rows).to_csv(csv, index=False)
        ran += 1; el = time.time() - t0
        say(f"    saved {f.name}; elapsed {el/60:.1f} min, estimated remaining {(len(runs)-k)*el/ran/60:.1f} min"); keras.backend.clear_session()
    df = pd.read_csv(csv); mc = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10"]
    agg = df.groupby(["model", "protocol"])[mc].agg(["mean", "std"]).round(4); agg["n_seeds"] = df.groupby(["model", "protocol"]).size()
    agg.to_csv(out / f"{tag}_summary.csv"); say("SUMMARY (mean / std over seeds)"); print(agg.to_string())
    return best
