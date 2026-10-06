"""E5 - Does attention add anything? Same data, same capacity, same recipe; only the attention part changes.
  A = paper model (custom TemporalAttention)   B = attention removed   C = Keras built-in MultiHeadAttention
For every (variant, seed): train (notebook recipe), evaluate default + strict with full-history masking, save per-user
arrays. Re-running skips finished runs, so it is safe to interrupt (Ctrl+C) and resume. For variant A it also saves
attention-weight statistics (how far from uniform the weights are).
Run:  python experiment-2-revision/experiments/e5_attention.py                       (3 variants x 10 seeds, ~20 min)
      python experiment-2-revision/experiments/e5_attention.py --variants A --seeds 42   (quick test)"""
import argparse, os, sys, time, warnings, json
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.provenance import start_run, say, save_json, ROOT, user_codes, order_digest
ap = argparse.ArgumentParser()
ap.add_argument("--variants", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202, 7, 13, 21, 34, 55, 89, 144])
ap.add_argument("--epochs", type=int, default=50); ap.add_argument("--batch-size", type=int, default=64)
ap.add_argument("--patience", type=int, default=5); ap.add_argument("--tag", default="e5")
args = ap.parse_args()
log, meta = start_run(f"{args.tag}_attention", args)

import numpy as np, pandas as pd, keras, tensorflow as tf
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.models import build_lstm_attention, TemporalAttention
from common.metrics import evaluate_scores

say("STEP 1  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)
MODE = {"A": "custom", "B": "none", "C": "mha"}
NAME = {"A": "A_custom_attention", "B": "B_no_attention", "C": "C_keras_mha"}
out = ROOT / "results"; pdir = out / f"{args.tag}_peruser"; pdir.mkdir(exist_ok=True)
runs = [(v, s) for s in args.seeds for v in args.variants]
say(f"STEP 2  {len(runs)} runs: variants {args.variants} x seeds {args.seeds}")
csv = out / f"{args.tag}_attention.csv"
rows = pd.read_csv(csv).to_dict("records") if csv.exists() else []
t_all = time.time(); done_now = 0

for k, (v, seed) in enumerate(runs, 1):
    f = pdir / f"{NAME[v]}_seed{seed}.npz"
    if f.exists():
        say(f"[{k}/{len(runs)}] {NAME[v]} seed {seed}: already done, skipping"); continue
    say(f"[{k}/{len(runs)}] {NAME[v]} seed {seed}: training")
    keras.utils.set_random_seed(seed)
    model = build_lstm_attention(D, seed=seed, attention=MODE[v])
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
        rows.append({"variant": NAME[v], "seed": seed, "protocol": nm, "params": model.count_params(),
                     "epochs_run": len(h.history["loss"]), "best_val_loss": min(h.history["val_loss"]),
                     **{kk: float(vv) for kk, vv in r.items()}})
        for kk, vv in pu.items(): arrays[f"{nm}_{kk}"] = vv
        arrays[f"{nm}_top10"] = top
        say(f"    {nm:8s} " + "  ".join(f"{kk}={float(vv):.4f}" for kk, vv in r.items() if kk != "Coverage@10"))
    for nm, (X, y, mt) in D.splits.items():
        arrays[f"{nm}_y"] = y; arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
    if v == "A":      # how peaked is the learned attention? (uniform over real courses = no selectivity)
        awm = keras.Model(model.inputs, model.get_layer("temporal_attention").output[1])
        w = awm.predict(D.X_test, batch_size=512, verbose=0); real = (D.X_test[0] != 0)
        n = real.sum(1); ent = -(np.where(w > 0, w * np.log(np.maximum(w, 1e-12)), 0)).sum(1)
        arrays["att_entropy_ratio"] = ent / np.log(np.maximum(n, 2))        # 1.0 = perfectly uniform
        arrays["att_max_weight"] = w.max(1); arrays["att_uniform_weight"] = 1.0 / np.maximum(n, 1)
        arrays["att_last_pos_weight"] = w[:, -1]; arrays["att_first_50_users"] = w[:50]
        say(f"    attention: mean entropy ratio={arrays['att_entropy_ratio'].mean():.3f} (1=uniform), "
            f"mean max weight={arrays['att_max_weight'].mean():.3f} vs uniform {arrays['att_uniform_weight'].mean():.3f}, "
            f"weight on most recent course={arrays['att_last_pos_weight'].mean():.3f}")
    np.savez_compressed(f, **arrays); pd.DataFrame(rows).to_csv(csv, index=False)
    done_now += 1; el = time.time() - t_all; left = (len(runs) - k) * el / max(done_now, 1)
    say(f"    saved {f.name}; elapsed {el/60:.1f} min, estimated remaining {left/60:.1f} min")
    del model; keras.backend.clear_session()

df = pd.read_csv(csv)
mc = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10"]
agg = df.groupby(["variant", "protocol"])[mc].agg(["mean", "std"]).round(4)
agg["n_seeds"] = df.groupby(["variant", "protocol"]).size()
agg.to_csv(out / f"{args.tag}_attention_summary.csv")
say("SUMMARY (mean / std over seeds)"); print(agg.to_string())
save_json({"meta": meta}, out / f"{args.tag}_attention_meta.json"); say("E5 DONE")
