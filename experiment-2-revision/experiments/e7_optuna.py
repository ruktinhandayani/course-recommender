"""E7 - budget-matched hyperparameter search (Optuna) for the four main backbones, then a 10-seed test evaluation of each tuned model.

Why: in E3-E5 SASRec and GRU4Rec were tuned on a small grid while the paper's LSTM (with and without attention) used a fixed architecture.
E7 gives every backbone the SAME search budget, the SAME objective and the SAME evaluation, so the backbone comparison (E6, Table 2) cannot be
explained by unequal tuning.

Models   a symmetric 3 x 2 design: each backbone WITHOUT and WITH the paper's temporal attention (TA), identical search budget for all six
         lstm_noattn / lstm_attn     paper LSTM, five inputs, attention removed (E5 B) / custom attention (E5 A, the paper model)
         gru4rec / gru4rec_ta        GRU4Rec-style, course sequence only (E3 / E3b course_only)
         sasrec / sasrec_ta          SASRec, course sequence only (E4 / E4b course_only)
         lstm_mha                    optional (add to --models): LSTM with Keras MultiHeadAttention (E5 C)
         Trial 0 of each study is that model's own E3-E5 configuration.
Search   Optuna study per model, `--trials` trials (default 30), TPE sampler (`--sampler random` = plain random search as a control).  Trial 0 is the
         configuration used in E3-E5, so the search can never end below the earlier setting on validation.  Search spaces are in SPACE below.
Objective validation Hit@10 (default protocol) [--objective both (E7b): the mean of validation Hit@10 and validation-strict Hit@10, see below], mean over `--tune-seeds` (default 42 and 101; two seeds so selection does not chase seed noise).
         The TEST set is not touched during the search.  Ties are irrelevant (continuous mean).
Final    best configuration of each study is trained for every seed in `--seeds` (default the ten published seeds) and evaluated once on the test set,
         default + strict protocol, full-history masking.  Same per-user npz layout as E3-E5, so e6_paired_ci.py can compare them.
Resume   studies live in sqlite files (results/<tag>_optuna/<model>.db); re-running continues unfinished studies and skips finished final runs.
Run      python experiment-2-revision/experiments/e7_optuna.py                    (full; several hours on the RTX 4070 SUPER, see the printed estimate)
         python experiment-2-revision/experiments/e7_optuna.py --quick            (smoke test; writes e7quick_* files)
Options  --models <any of the seven names above>   --trials 30   --tune-seeds 42 101   --seeds ...   --sampler tpe|random   --optuna-seed 0
         --tag NAME   --epochs 50 --batch-size 64 --patience 5   --skip-final (search only)
Needs    pip install optuna   (into venv_stitch; then add it to requirements-exp.lock.txt)"""
import argparse, json, os, sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ALL = ["lstm_attn", "lstm_noattn", "gru4rec", "gru4rec_ta", "sasrec", "sasrec_ta", "lstm_mha"]
MAIN = ALL[:6]          # 3 backbones x {without, with the paper's temporal attention}; lstm_mha (Keras MHA, E5 variant C) is optional
ap = argparse.ArgumentParser()
ap.add_argument("--models", nargs="+", default=MAIN, choices=ALL)
ap.add_argument("--trials", type=int, default=30)
ap.add_argument("--tune-seeds", nargs="+", type=int, default=[42, 101])
ap.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202, 7, 13, 21, 34, 55, 89, 144])
ap.add_argument("--sampler", choices=["tpe", "random"], default="tpe")
ap.add_argument("--optuna-seed", type=int, default=0)
ap.add_argument("--epochs", type=int, default=50); ap.add_argument("--batch-size", type=int, default=64); ap.add_argument("--patience", type=int, default=5)
ap.add_argument("--tag", default=None, help="result name prefix (default e7, or e7random with --sampler random)")
ap.add_argument("--objective", choices=["default", "both"], default="default",
                help="default: validation Hit@10 (E7). both: mean of validation Hit@10 and validation-STRICT Hit@10 (E7b; history skips the course adjacent to the target)")
ap.add_argument("--skip-final", action="store_true", help="search only, no test evaluation")
ap.add_argument("--quick", action="store_true", help="smoke test: 2 trials, 1 tuning seed, 3 epochs, 1 final seed; tag e7quick")
args = ap.parse_args()
_base = "e7b" if args.objective == "both" else "e7"
TAG = args.tag or (_base if args.sampler == "tpe" else _base + "random")
if args.quick:
    TAG += "quick"; args.trials, args.tune_seeds, args.epochs, args.seeds = 2, [42], 3, [42]
from common.provenance import start_run, say, save_json, ROOT, order_digest
log, meta = start_run(TAG, args)
try:
    import optuna
except ImportError:
    sys.exit("optuna is not installed: run  /data/Documents/Bu-Ruktin/03/venv_stitch/bin/python -m pip install optuna")
import numpy as np, pandas as pd, keras
from common.data_pipeline import build_dataset
from common.contract import assert_contract
from common.metrics import evaluate_scores
from common.models import build_lstm_attention, build_gru4rec, build_gru4rec_ta, build_sasrec, build_sasrec_ta
optuna.logging.set_verbosity(optuna.logging.WARNING)

say("STEP 1  dataset + contract"); D = build_dataset(); assert_contract(D, raw=True)
if args.objective == "both":
    # validation analogue of the strict protocol: history = train core WITHOUT its last course, target = the validation target (same construction as the x1 audit)
    from common.data_pipeline import _make_holdout, seen_matrix
    X_vs, y_vs, meta_vs = _make_holdout(D.train_enc[D.train_enc.duplicated("user_id", keep="last")], D.val_enc, "validation_strict")
    seen_vs = seen_matrix(meta_vs, D.num_courses)
    say(f"  validation-strict set: {len(y_vs)} of {len(D.y_val)} validation users (those whose train core has >= 3 courses)")
    assert 3000 < len(y_vs) <= len(D.y_val), "unexpected size of the validation-strict set"
OUT = ROOT / "results"; ODIR = OUT / f"{TAG}_optuna"; ODIR.mkdir(exist_ok=True)

# ---- search spaces and the configuration used in E3-E5 (trial 0) --------------------------------------------------------------------
DEFAULT = {"gru4rec_ta": {"emb": 96, "units": 64, "dropout": 0.2, "lr": 1e-3}, "sasrec_ta": {"d": 96, "blocks": 1, "heads": 2, "dropout": 0.2, "lr": 1e-3},
           "lstm_mha": {"course_dim": 96, "comp_dim": 32, "latent": 192, "dropout": 0.3, "lr": 1e-3},
           "lstm_attn": {"course_dim": 96, "comp_dim": 32, "latent": 192, "dropout": 0.3, "lr": 1e-3},
           "lstm_noattn": {"course_dim": 96, "comp_dim": 32, "latent": 192, "dropout": 0.3, "lr": 1e-3},
           "gru4rec": {"emb": 96, "units": 192, "dropout": 0.2, "lr": 1e-3},
           "sasrec": {"d": 96, "blocks": 2, "heads": 2, "dropout": 0.2, "lr": 1e-3}}
SPACE = {"lstm_attn": "course_dim {64,96,128}, comp_dim {16,32}, latent {128,192,256}, dropout U[0.1,0.5], lr logU[3e-4,3e-3]",
         "gru4rec": "emb {64,96,128}, units {64,128,192,256}, dropout U[0.1,0.5], lr logU[3e-4,3e-3]",
         "sasrec": "d {64,96,128}, blocks {1,2,3}, heads {2,4}, dropout U[0.1,0.5], lr logU[3e-4,3e-3]"}
SPACE["lstm_noattn"] = SPACE["lstm_mha"] = SPACE["lstm_attn"]; SPACE["gru4rec_ta"] = SPACE["gru4rec"]; SPACE["sasrec_ta"] = SPACE["sasrec"]


def suggest(name, t):
    lr, dr = t.suggest_float("lr", 3e-4, 3e-3, log=True), t.suggest_float("dropout", 0.1, 0.5)
    if name.startswith("lstm"):
        return {"course_dim": t.suggest_categorical("course_dim", [64, 96, 128]), "comp_dim": t.suggest_categorical("comp_dim", [16, 32]),
                "latent": t.suggest_categorical("latent", [128, 192, 256]), "dropout": dr, "lr": lr}
    if name.startswith("gru4rec"):
        return {"emb": t.suggest_categorical("emb", [64, 96, 128]), "units": t.suggest_categorical("units", [64, 128, 192, 256]), "dropout": dr, "lr": lr}
    return {"d": t.suggest_categorical("d", [64, 96, 128]), "blocks": t.suggest_categorical("blocks", [1, 2, 3]),
            "heads": t.suggest_categorical("heads", [2, 4]), "dropout": dr, "lr": lr}


def build(name, cfg, seed):
    if name == "lstm_attn": return build_lstm_attention(D, cfg=cfg, seed=seed, attention="custom")
    if name == "lstm_noattn": return build_lstm_attention(D, cfg=cfg, seed=seed, attention="none")
    if name == "lstm_mha": return build_lstm_attention(D, cfg=cfg, seed=seed, attention="mha")
    m = {"gru4rec": build_gru4rec, "gru4rec_ta": build_gru4rec_ta, "sasrec": build_sasrec, "sasrec_ta": build_sasrec_ta}[name](D, "course_only", cfg)
    m.compile(optimizer=keras.optimizers.Adam(learning_rate=cfg["lr"]), loss="sparse_categorical_crossentropy")
    return m


def X_of(name, X):
    return X if name.startswith("lstm") else X[:1]


def train(name, cfg, seed):
    keras.utils.set_random_seed(seed)
    m = build(name, cfg, seed)
    h = m.fit(X_of(name, D.X_train), D.y_train, validation_data=(X_of(name, D.X_val), D.y_val), epochs=args.epochs, batch_size=args.batch_size, shuffle=True, verbose=0,
              callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", mode="min", patience=args.patience, restore_best_weights=True),
                         keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)])
    return m, h


# ---- STEP 2: search ------------------------------------------------------------------------------------------------------------------
say(f"STEP 2  Optuna search ({args.sampler}, seed {args.optuna_seed}): {args.trials} trials x {len(args.tune_seeds)} tuning seeds per model; models {args.models}")
studies, t_start = {}, time.time()
for name in args.models:
    sampler = optuna.samplers.TPESampler(seed=args.optuna_seed, multivariate=True, n_startup_trials=min(8, max(args.trials // 3, 1))) if args.sampler == "tpe" \
        else optuna.samplers.RandomSampler(seed=args.optuna_seed)
    st = optuna.create_study(study_name=f"{TAG}_{name}", storage=f"sqlite:///{ODIR / (name + '.db')}", sampler=sampler, direction="maximize", load_if_exists=True)
    studies[name] = st
    done = len([t for t in st.trials if t.state.is_finished()])
    if done == 0: st.enqueue_trial(DEFAULT[name])                       # trial 0 = the E3-E5 configuration
    say(f"  [{name}] space: {SPACE[name]}; finished trials so far: {done}")

    def objective(trial, name=name):
        t0 = time.time(); cfg = suggest(name, trial); vh, vm, ep, pc, vd, vs = [], [], [], 0, [], []
        for s in args.tune_seeds:
            m, h = train(name, cfg, s)
            r, _, _ = evaluate_scores(m.predict(X_of(name, D.X_val), batch_size=512, verbose=0), D.seen_val, D.y_val, D.num_courses)
            vd.append(float(r["Hit@10"]))
            if args.objective == "both":
                rs, _, _ = evaluate_scores(m.predict(X_of(name, X_vs), batch_size=512, verbose=0), seen_vs, y_vs, D.num_courses); vs.append(float(rs["Hit@10"]))
            vh.append(vd[-1] if args.objective == "default" else 0.5 * (vd[-1] + vs[-1])); vm.append(float(r["MRR@10"])); ep.append(len(h.history["loss"])); pc = m.count_params(); keras.backend.clear_session()
        trial.set_user_attr("val_MRR@10", float(np.mean(vm))); trial.set_user_attr("params", int(pc)); trial.set_user_attr("epochs", ep)
        trial.set_user_attr("val_Hit@10_by_seed", vh); trial.set_user_attr("val_default_Hit@10", float(np.mean(vd)))
        if vs: trial.set_user_attr("val_strict_Hit@10", float(np.mean(vs)))
        trial.set_user_attr("sec", round(time.time() - t0, 1))
        say(f"  [{name}] trial {trial.number:02d}  objective={np.mean(vh):.4f}" + (f" (val default {np.mean(vd):.4f}, val strict {np.mean(vs):.4f})" if vs else "") + f"  (seeds {', '.join(f'{v:.4f}' for v in vh)})  MRR@10={np.mean(vm):.4f}  params={pc:,}  "
            f"{time.time() - t0:.0f}s  {cfg}")
        return float(np.mean(vh))

    while len([t for t in st.trials if t.state.is_finished()]) < args.trials:
        st.optimize(objective, n_trials=1)
    best = st.best_trial; base = st.trials[0].value
    say(f"  [{name}] BEST trial {best.number}: objective={best.value:.4f} (E3-E5 configuration: {base:.4f}, gain {best.value - base:+.4f})  {best.params}")
    say(f"  elapsed {(time.time() - t_start) / 60:.1f} min")

trial_rows, best_out = [], {}
for name, st in studies.items():
    for t in st.trials:
        if t.state.is_finished():
            trial_rows.append({"model": name, "trial": t.number, "state": t.state.name, "val_Hit@10": t.value, "val_MRR@10": t.user_attrs.get("val_MRR@10"), "val_default_Hit@10": t.user_attrs.get("val_default_Hit@10"), "val_strict_Hit@10": t.user_attrs.get("val_strict_Hit@10"),
                               "params": t.user_attrs.get("params"), "epochs": json.dumps(t.user_attrs.get("epochs")), "is_default_config": t.number == 0,
                               **{f"cfg_{k}": v for k, v in t.params.items()}})
    b = st.best_trial
    best_out[name] = {"cfg": {**DEFAULT[name], **b.params}, "best_trial": b.number, "val_Hit@10": b.value, "val_Hit@10_E3_E5_config": st.trials[0].value,
                      "n_trials": len([t for t in st.trials if t.state.is_finished()]), "objective": args.objective}
pd.DataFrame(trial_rows).to_csv(OUT / f"{TAG}_trials.csv", index=False)
(OUT / f"{TAG}_best.json").write_text(json.dumps(best_out, indent=2))
say(f"  wrote {TAG}_trials.csv and {TAG}_best.json")
if args.skip_final:
    save_json({"meta": meta, "spaces": SPACE, "default": DEFAULT, "best": best_out}, OUT / f"{TAG}_meta.json"); say(f"{TAG} DONE (search only)"); sys.exit(0)

# ---- STEP 3: final runs on all seeds, test evaluated once ----------------------------------------------------------------------------
pdir = OUT / f"{TAG}_peruser"; pdir.mkdir(exist_ok=True)
NAME = {n: f"{n}_tuned" for n in ALL}
runs = [(n, s) for s in args.seeds for n in args.models]
say(f"STEP 3  {len(runs)} final runs: models {args.models} x seeds {args.seeds}")
csv = OUT / f"{TAG}.csv"; rows = pd.read_csv(csv).to_dict("records") if csv.exists() else []
t0, ran = time.time(), 0
for k, (name, seed) in enumerate(runs, 1):
    f = pdir / f"{NAME[name]}_seed{seed}.npz"
    if f.exists(): say(f"[{k}/{len(runs)}] {NAME[name]} seed {seed}: already done, skipping"); continue
    cfg = best_out[name]["cfg"]; say(f"[{k}/{len(runs)}] {NAME[name]} seed {seed}: training {cfg}")
    m, h = train(name, cfg, seed); arrays = {}
    for nm, (X, y, mt) in D.splits.items():
        r, pu, top = evaluate_scores(m.predict(X_of(name, X), batch_size=512, verbose=0), D.seen[nm], y, D.num_courses)
        rows.append({"model": NAME[name], "seed": seed, "protocol": nm, "cfg": json.dumps(cfg), "params": m.count_params(), "epochs_run": len(h.history["loss"]),
                     "best_val_loss": min(h.history["val_loss"]), **{kk: float(vv) for kk, vv in r.items()}})
        for kk, vv in pu.items(): arrays[f"{nm}_{kk}"] = vv
        arrays[f"{nm}_top10"], arrays[f"{nm}_y"] = top, y; arrays[f"{nm}_order_sha256"] = np.array(order_digest(mt["user_id"]))
        say(f"    {nm:8s} " + "  ".join(f"{kk}={float(vv):.4f}" for kk, vv in r.items() if kk != "Coverage@10"))
    if name in ("lstm_attn", "gru4rec_ta", "sasrec_ta"):               # same attention diagnostics as E5 variant A / E3b / E4b
        w = keras.Model(m.inputs, m.get_layer("temporal_attention").output[1]).predict(X_of(name, D.X_test), batch_size=512, verbose=0); n = (D.X_test[0] != 0).sum(1)
        arrays["att_entropy_ratio"] = (-(np.where(w > 0, w * np.log(np.maximum(w, 1e-12)), 0)).sum(1)) / np.log(np.maximum(n, 2))
        arrays["att_max_weight"], arrays["att_uniform_weight"], arrays["att_last_pos_weight"] = w.max(1), 1.0 / np.maximum(n, 1), w[:, -1]
    np.savez_compressed(f, **arrays); pd.DataFrame(rows).to_csv(csv, index=False)
    ran += 1; el = time.time() - t0
    say(f"    saved {f.name}; elapsed {el / 60:.1f} min, estimated remaining {(len(runs) - k) * el / ran / 60:.1f} min"); keras.backend.clear_session()

df = pd.read_csv(csv); mc = ["Hit@1", "Hit@5", "Hit@10", "MRR@10", "NDCG@10"]
agg = df.groupby(["model", "protocol"])[mc].agg(["mean", "std"]).round(4); agg["n_seeds"] = df.groupby(["model", "protocol"]).size()
agg.to_csv(OUT / f"{TAG}_summary.csv"); say("SUMMARY (mean / std over seeds)"); print(agg.to_string())
save_json({"meta": meta, "spaces": SPACE, "default": DEFAULT, "best": best_out}, OUT / f"{TAG}_meta.json"); say(f"{TAG} DONE")
