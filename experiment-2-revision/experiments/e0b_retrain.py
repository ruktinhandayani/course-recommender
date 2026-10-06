"""E0b - RETRAIN the H2 model with the notebook's training recipe and compare with the published numbers.
Recipe (notebook cells 46-48): Adam 1e-3, up to 50 epochs, batch 64, EarlyStopping(val_loss, patience 5, restore best),
ReduceLROnPlateau(factor .5, patience 2, min_lr 1e-5), shuffle. Evaluated with full-history masking on both protocols.
Run:  python experiment-2-revision/experiments/e0b_retrain.py --seed 42
Watch:  tail -f experiment-2-revision/logs/e0b_retrain_*.log     (and in another terminal: watch -n 2 nvidia-smi)"""
import argparse, os, sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.provenance import start_run, say, save_json, ROOT, user_codes, order_digest
ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--epochs", type=int, default=50)
ap.add_argument("--batch-size", type=int, default=64)
ap.add_argument("--patience", type=int, default=5)
ap.add_argument("--tag", default="e0b")
ap.add_argument("--skip-contract", action="store_true", help="only for smoke tests; never for reported results")
args = ap.parse_args()
log, meta = start_run(f"{args.tag}_retrain_seed{args.seed}", args)

import numpy as np, keras, tensorflow as tf
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.models import build_lstm_attention
from common.metrics import evaluate_scores

say("STEP 1/4  build dataset + contract check")
D = build_dataset()
if not args.skip_contract:
    assert_contract(D, raw=True)

say(f"STEP 2/4  build model, seed={args.seed}")
keras.utils.set_random_seed(args.seed)
model = build_lstm_attention(D, seed=args.seed)
model.summary(print_fn=lambda s: print(s))


class Monitor(keras.callbacks.Callback):
    def on_train_begin(self, logs=None):
        self.t0 = time.time(); say(f"training start: {len(D.y_train)} sequences, {len(D.y_val)} validation, batch {args.batch_size}")
    def on_epoch_end(self, epoch, logs=None):
        lr = float(keras.ops.convert_to_numpy(self.model.optimizer.learning_rate))
        say(f"epoch {epoch+1:02d}/{args.epochs}  loss={logs['loss']:.4f}  val_loss={logs['val_loss']:.4f}  lr={lr:.6f}  elapsed={time.time()-self.t0:.0f}s")


say("STEP 3/4  training")
hist = model.fit(D.X_train, D.y_train, validation_data=(D.X_val, D.y_val), epochs=args.epochs, batch_size=args.batch_size,
                 shuffle=True, verbose=0,
                 callbacks=[Monitor(),
                            keras.callbacks.EarlyStopping(monitor="val_loss", mode="min", patience=args.patience, restore_best_weights=True),
                            keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)])
best = int(np.argmin(hist.history["val_loss"])) + 1
say(f"training finished after {len(hist.history['loss'])} epochs; best epoch {best}, val_loss={min(hist.history['val_loss']):.4f}")

say("STEP 4/4  evaluation (full pre-target history masking)")
PUB = {"default": {"Hit@1": 0.5998, "Hit@5": 0.8386, "Hit@10": 0.9273, "MRR@10": 0.7011, "NDCG@10": 0.7552},
       "strict": {"Hit@1": 0.1206, "Hit@5": 0.7704, "Hit@10": 0.8842, "MRR@10": 0.4177, "NDCG@10": 0.5330}}
TOL = {"Hit@1": 0.015, "Hit@5": 0.01, "Hit@10": 0.005, "MRR@10": 0.01, "NDCG@10": 0.01}
res, arrays, flags = {}, {}, []
for nm, (X, y, mt) in D.splits.items():
    r, pu, top = evaluate_scores(model.predict(X, batch_size=512, verbose=0), D.seen[nm], y, D.num_courses)
    res[nm] = {k: float(v) for k, v in r.items()}
    for k, v in pu.items():
        arrays[f"{nm}_{k}"] = v
    arrays[f"{nm}_top10"] = top; arrays[f"{nm}_y"] = y
    arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
    codes = user_codes(mt["user_id"])
    if codes: arrays[f"{nm}_user_code"] = np.array(codes)       # pseudonym only; raw IDs are never written
    for k, pub in PUB[nm].items():
        d = r[k] - pub; within = abs(d) <= TOL[k]; flags.append(within)
        say(f"  {nm:8s} {k:8s} mine={r[k]:.4f}  published={pub:.4f}  diff={d:+.4f}  {'within tolerance' if within else 'OUTSIDE tolerance'}")
out = ROOT / "results"
np.savez_compressed(out / f"{args.tag}_seed{args.seed}_peruser.npz", **arrays)
save_json({"meta": meta, "metrics": res, "epochs_run": len(hist.history["loss"]), "best_epoch": best,
           "val_loss_history": hist.history["val_loss"], "within_tolerance": bool(all(flags))}, out / f"{args.tag}_seed{args.seed}.json")
say("E0b " + ("PASSED: retrain matches the published numbers within tolerance." if all(flags) else
              "NOTE: some metrics are outside tolerance - report this log back before continuing."))
