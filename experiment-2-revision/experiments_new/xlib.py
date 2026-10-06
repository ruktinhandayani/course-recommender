"""xlib - shared code for the improvement study (x1_*). Everything new lives in experiments_new/; common/ is untouched.

What it adds on top of common/:
  * build_features(D): timestamp-derived side information that the published pipeline discards but that exists in the raw
    data (event_timestamp).  It uses ONLY information available at prediction time: the timestamps of the user's own history
    and the platform's PAST enrolment activity (events with timestamp <= the user's last history timestamp, train core only).
    The timestamp of the target is never used.  Alignment with D.X_* is asserted (self-verifying).
  * build_model(D, cfg): a configurable SASRec (+ optional time-gap input, calendar embedding, candidate-time prior,
    auxiliary competency/level heads, label smoothing) whose switches are the ablation factors.
  * train_eval(...): same recipe as common/runner.fit (Adam 1e-3, batch 64, <=50 epochs, EarlyStopping(val_loss, patience 5,
    restore best), ReduceLROnPlateau) so numbers are comparable with e4.
"""
import sys, json, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import keras, tensorflow as tf
from common.metrics import evaluate_scores
from common.provenance import say

L = 10
T0 = pd.Timestamp("2023-07-01")
W_SHORT, W_LONG = 7.0, 30.0           # days, windows of the "trending" statistics (past only)


def days(ts):
    return ((pd.to_datetime(ts) - T0).dt.total_seconds() / 86400.0).to_numpy()


def _pad_pre_f(seqs, maxlen=L):
    out = np.zeros((len(seqs), maxlen), dtype="float32")
    for i, s in enumerate(seqs):
        s = list(s)[-maxlen:]
        if s:
            out[i, -len(s):] = s
    return out


# ----------------------------------------------------------------------------------------------- features
class Feats:
    """Per split: time-gap features (N,L,2), calendar month of last event (N,), candidate prior features (N,V,F), aux targets."""


def build_features(D):
    tr = D.train_enc
    ev_days = days(tr["sort_timestamp"])
    V = D.num_courses
    per_course = [np.sort(ev_days[tr["course_encoded"].to_numpy() == c]) for c in range(V)]
    launch = np.array([p[0] if len(p) else np.inf for p in per_course])         # first train-core enrolment per course

    # recent-transition table: for every consecutive pair (a -> b) inside a user's train core, the time at which b happened
    ts_sorted = tr.assign(_d=ev_days).sort_values(["user_id", "_d"])
    nxt_c = ts_sorted.groupby("user_id")["course_encoded"].shift(-1); nxt_t = ts_sorted.groupby("user_id")["_d"].shift(-1)
    ok = nxt_c.notna().to_numpy()
    tr_from, tr_to, tr_t = ts_sorted["course_encoded"].to_numpy()[ok], nxt_c.to_numpy()[ok].astype(int), nxt_t.to_numpy()[ok]
    pair_t = {}
    for a, b, t in zip(tr_from, tr_to, tr_t):
        pair_t.setdefault((a, b), []).append(t)
    pair_t = {k: np.sort(np.array(v)) for k, v in pair_t.items()}
    W_TRANS = 60.0

    def trans_feats(c_last, t_last):                                              # (N,V): recent a->b transitions completed by t_last
        out = np.zeros((len(t_last), V), dtype="float32")
        for (a, b), p in pair_t.items():
            idx = np.nonzero(c_last == a)[0]
            if len(idx):
                tl = t_last[idx]
                out[idx, b] = np.log1p(np.searchsorted(p, tl, side="right") - np.searchsorted(p, tl - W_TRANS, side="right"))
        return out / 5.0

    def cand_feats(t_last, c_last):                                              # (N,V,5), all past-only
        N = len(t_last); F = np.zeros((N, V, 5), dtype="float32")
        F[:, :, 4] = trans_feats(c_last, t_last)
        for c in range(1, V):
            p = per_course[c]
            hi = np.searchsorted(p, t_last, side="right")
            F[:, c, 0] = np.log1p(hi - np.searchsorted(p, t_last - W_SHORT, side="right"))
            F[:, c, 1] = np.log1p(hi - np.searchsorted(p, t_last - W_LONG, side="right"))
            launched = (launch[c] <= t_last)
            F[:, c, 2] = launched
            F[:, c, 3] = np.where(launched, np.log1p(np.maximum(t_last - launch[c], 0)), 0.0) / 6.0
        F[:, :, :2] /= 5.0
        return F

    def pack(course_seqs, ts_seqs, y_aux_comp, y_aux_lvl, X_course, label):
        ts = _pad_pre_f(ts_seqs); real = X_course != 0
        assert ((ts != 0) == real).all(), f"{label}: timestamp/course padding mismatch"
        prev = np.concatenate([ts[:, :1], ts[:, :-1]], 1)
        pv = np.concatenate([np.zeros((len(ts), 1), bool), real[:, :-1]], 1)
        gap = np.where(real & pv, np.log1p(np.maximum(ts - prev, 0)), 0.0) / 6.0     # log-days gap to previous item
        t_last = ts[:, -1].astype("float64")
        age = np.where(real, np.log1p(np.maximum(t_last[:, None] - ts, 0)), 0.0) / 6.0   # how long ago each item was taken
        month = np.clip((t_last // 30.4).astype(int) + 1, 0, 40)
        f = {"tfeat": np.stack([gap, age], -1).astype("float32"), "month": month.astype("int32"), "cand": cand_feats(t_last, X_course[:, -1])}
        f["t_last"] = t_last
        return f

    # ---- training prefixes (same enumeration order as data_pipeline cell 34)
    ts_g = tr.groupby("user_id").agg({"course_encoded": list, "competency_encoded": list, "level_encoded": list}).reset_index()
    tsd = tr.assign(_d=ev_days).groupby("user_id")["_d"].apply(list)
    cs, tss, yk, yl, ttg = [], [], [], [], []
    for _, r in ts_g.iterrows():
        c, d = r["course_encoded"], tsd.loc[r["user_id"]]
        for i in range(1, len(c)):
            cs.append(c[:i]); tss.append(d[:i]); ttg.append(d[i]); yk.append(r["competency_encoded"][i]); yl.append(r["level_encoded"][i])
    out = {"train": pack(cs, tss, None, None, D.X_train[0], "train")}
    out["train"]["aux"] = (np.array(yk), np.array(yl)); out["train"]["t_target"] = np.array(ttg)   # t_target: audit only, never a model input
    assert len(yk) == len(D.y_train)

    def holdout(hist_df, target_df, meta, X, y, label):
        hd = hist_df.assign(_d=ev_days if hist_df is tr else days(hist_df["sort_timestamp"])).groupby("user_id")["_d"].apply(list)
        tg = target_df.set_index("user_id")
        tss = [hd.loc[u] for u in meta["user_id"]]
        f = pack(None, tss, None, None, X[0], label)
        f["t_target"] = days(tg.loc[meta["user_id"], "sort_timestamp"])
        f["aux"] = (tg.loc[meta["user_id"], "competency_encoded"].to_numpy(), tg.loc[meta["user_id"], "level_encoded"].to_numpy())
        assert (tg.loc[meta["user_id"], "course_encoded"].to_numpy() == y).all(), f"{label}: target mismatch"
        return f

    out["val"] = holdout(tr, D.val_enc, D.meta_val, D.X_val, D.y_val, "val")
    out["vstrict"] = val_strict(D, tr, ev_days, pack)
    out["default"] = holdout(D.pretest_enc, D.test_enc, D.meta_test, D.X_test, D.y_test, "default")
    out["strict"] = holdout(tr, D.test_enc, D.meta_test_strict, D.X_test_strict, D.y_test_strict, "strict")
    return out


def val_strict(D, tr, ev_days, pack):
    """VALIDATION analogue of the strict protocol (history that skips the course adjacent to the target): history = train core
    without its last course, target = the validation target.  Only users whose train core has >= 3 courses (history >= 2) exist,
    so this subset is a directional check, not an exact replica (users with a 2-course train core cannot be represented)."""
    from common.data_pipeline import pad_pre
    g = tr.assign(_d=ev_days).groupby("user_id").agg(c=("course_encoded", list), d=("_d", list), k=("competency_encoded", list), l=("level_encoded", list))
    vt = D.val_enc.set_index("user_id")
    users = [u for u in D.meta_val["user_id"] if len(g.loc[u, "c"]) >= 3]
    hc = [g.loc[u, "c"][:-1] for u in users]; hd = [g.loc[u, "d"][:-1] for u in users]
    X = pad_pre(hc); y = vt.loc[users, "course_encoded"].to_numpy()
    f = pack(None, hd, None, None, X, "vstrict")
    f["_X"], f["_y"] = X, y
    seen = np.zeros((len(users), D.num_courses), dtype=bool)
    for i, h in enumerate(hc):
        seen[i, h] = True
    f["_seen"] = seen; f["t_target"] = days(vt.loc[users, "sort_timestamp"])
    f["aux"] = (vt.loc[users, "competency_encoded"].to_numpy(), vt.loc[users, "level_encoded"].to_numpy()); f["users"] = users
    return f


# ----------------------------------------------------------------------------------------------- model
@keras.saving.register_keras_serializable(package="CRE")
class XSASRec(keras.layers.Layer):
    """SASRec encoder (same as common.models.SASRecEncoder) with optional time-gap input and calendar embedding."""

    def __init__(self, V, d, blocks, heads, dropout, time_seq=False, calendar=False, **kw):
        super().__init__(**kw)
        self.d, self.blocks, self.time_seq, self.calendar = d, blocks, time_seq, calendar
        K = keras.layers
        self.item, self.pos = K.Embedding(V, d), K.Embedding(L, d)
        if time_seq:
            self.tproj = keras.Sequential([K.Dense(d // 2, activation="relu"), K.Dense(d)])
        if calendar:
            self.cal = K.Embedding(42, d)
        self.drop = K.Dropout(dropout)
        self.mha = [K.MultiHeadAttention(heads, d // heads, dropout=dropout) for _ in range(blocks)]
        self.ln1 = [K.LayerNormalization(epsilon=1e-6) for _ in range(blocks)]
        self.ln2 = [K.LayerNormalization(epsilon=1e-6) for _ in range(blocks)]
        self.f1 = [K.Dense(d, activation="relu") for _ in range(blocks)]
        self.f2 = [K.Dense(d) for _ in range(blocks)]
        self.ln_out = K.LayerNormalization(epsilon=1e-6)

    def call(self, inputs, training=None):
        course, tfeat, month = inputs
        x = self.item(course) * (self.d ** 0.5)
        if self.time_seq:
            x = x + self.tproj(tfeat)
        x = x + self.pos(tf.range(L))[None]
        if self.calendar:
            x = x + self.cal(month)[:, None, :]
        x = self.drop(x, training=training)
        real = tf.not_equal(course, 0)
        causal = tf.cast(tf.linalg.band_part(tf.ones((L, L)), -1, 0), tf.bool)
        mask = tf.logical_and(causal[None], real[:, None, :])
        keep = tf.cast(real[..., None], x.dtype)
        for i in range(self.blocks):
            q = self.ln1[i](x)
            x = x + self.drop(self.mha[i](q, q, attention_mask=mask, training=training), training=training)
            x = x + self.drop(self.f2[i](self.drop(self.f1[i](self.ln2[i](x)), training=training)), training=training)
            x = x * keep
        return self.ln_out(x)[:, -1, :]


@keras.saving.register_keras_serializable(package="CRE")
class CandidatePrior(keras.layers.Layer):
    """Per-course additive logit bias from past-only platform activity: bias[u,c] = sum_f W[c,f]*cand[u,c,f] + w_f*cand[u,c,f]."""

    def build(self, shape):
        V, F = shape[1], shape[2]
        self.W = self.add_weight(shape=(V, F), initializer="zeros", name="per_course")
        self.g = self.add_weight(shape=(F,), initializer="zeros", name="global")

    def call(self, cand):
        return tf.einsum("nvf,vf->nv", cand, self.W) + tf.einsum("nvf,f->nv", cand, self.g)


DEFAULT = dict(cand_cols=None, d=96, blocks=2, heads=2, dropout=0.2, time_seq=False, calendar=False, cand=False, aux=0.0, ls=0.0, lr=1e-3)


def build_model(D, cfg):
    c = {**DEFAULT, **cfg}
    K = keras.layers; V = D.num_courses
    i_course, i_t, i_m = K.Input((L,), name="course_input"), K.Input((L, 2), name="tfeat"), K.Input((), dtype="int32", name="month")
    i_cand = K.Input((V, 5), name="cand")
    h = XSASRec(V, c["d"], c["blocks"], c["heads"], c["dropout"], c["time_seq"], c["calendar"], name="sasrec_encoder")([i_course, i_t, i_m])
    hd = K.Dropout(c["dropout"])(h)
    logits = K.Dense(V, name="logits")(hd)
    if c["cand"]:
        cols = c["cand_cols"] if c["cand_cols"] is not None else [0, 1, 2, 3]
        sel = keras.layers.Lambda(lambda z: keras.ops.take(z, cols, axis=-1), output_shape=(V, len(cols)), name="cand_select")(i_cand)
        logits = K.Add()([logits, CandidatePrior(name="cand_prior")(sel)])
    out = K.Activation("softmax", name="course_prediction")(logits)
    outs = [out]
    if c["aux"] > 0:
        outs += [K.Dense(D.num_competencies, activation="softmax", name="aux_comp")(hd),
                 K.Dense(D.num_levels, activation="softmax", name="aux_level")(hd)]
    m = keras.Model([i_course, i_t, i_m, i_cand], outs)
    loss = {"course_prediction": keras.losses.SparseCategoricalCrossentropy()}
    if c["ls"] > 0:        # label smoothing on the main head (one-hot form)
        loss = {"course_prediction": _LSCE(V, c["ls"])}
    w = {"course_prediction": 1.0}
    if c["aux"] > 0:
        loss.update({"aux_comp": keras.losses.SparseCategoricalCrossentropy(), "aux_level": keras.losses.SparseCategoricalCrossentropy()})
        w.update({"aux_comp": c["aux"], "aux_level": c["aux"]})
    m.compile(optimizer=keras.optimizers.Adam(c["lr"]), loss=loss, loss_weights=w)
    return m


class _LSCE(keras.losses.Loss):
    def __init__(self, V, ls, **kw):
        super().__init__(**kw); self.V, self.ls = V, ls

    def call(self, y, p):
        y = tf.cast(tf.reshape(y, [-1]), tf.int32)
        oh = tf.one_hot(y, self.V) * (1 - self.ls) + self.ls / self.V
        return -tf.reduce_sum(oh * tf.math.log(tf.clip_by_value(p, 1e-9, 1.0)), -1)


def inputs_of(F):
    return [F["_X"], F["tfeat"], F["month"], F["cand"]]


def attach(D, FE):
    """Attach the course sequences to the feature dicts so that inputs_of(F) works."""
    FE["train"]["_X"], FE["train"]["_y"] = D.X_train[0], D.y_train
    FE["val"]["_X"], FE["val"]["_y"] = D.X_val[0], D.y_val
    FE["default"]["_X"], FE["default"]["_y"] = D.X_test[0], D.y_test
    FE["strict"]["_X"], FE["strict"]["_y"] = D.X_test_strict[0], D.y_test_strict
    return FE


def train_eval(D, FE, cfg, seed, epochs=50, patience=5, batch=64, splits=("val",), tag="", verbose=False, return_probs=False, augment=0.0):
    """Train one model, return metrics per requested split (+ val probs when asked). splits may include 'default','strict' (TEST)."""
    c = {**DEFAULT, **cfg}
    keras.utils.set_random_seed(seed)
    m = build_model(D, cfg)
    tr, va = FE["train"], FE["val"]
    ytr = [tr["_y"]] + ([tr["aux"][0], tr["aux"][1]] if c["aux"] > 0 else [])
    yva = [va["_y"]] + ([va["aux"][0], va["aux"][1]] if c["aux"] > 0 else [])
    mon = "val_course_prediction_loss" if c["aux"] > 0 else "val_loss"
    cbs = [keras.callbacks.EarlyStopping(monitor=mon, mode="min", patience=patience, restore_best_weights=True),
           keras.callbacks.ReduceLROnPlateau(monitor=mon, mode="min", factor=0.5, patience=2, min_lr=1e-5)]
    Xtr = inputs_of(tr)
    t0 = time.time()
    if augment > 0:
        h = _fit_aug(m, tr, va, ytr, yva, augment, epochs, batch, cbs, mon)
    else:
        h = m.fit(Xtr, ytr, validation_data=(inputs_of(va), yva), epochs=epochs, batch_size=batch, shuffle=True, verbose=0, callbacks=cbs)
    res = {"epochs": len(h.history["loss"]), "best_val_loss": float(min(h.history[mon])), "params": m.count_params(), "sec": time.time() - t0}
    probs = {}
    for s in splits:
        F = FE[s]; p = m.predict(inputs_of(F), batch_size=512, verbose=0)
        p = p[0] if isinstance(p, (list, tuple)) else p
        seen = F["_seen"] if "_seen" in F else {"val": D.seen_val, "default": D.seen_test, "strict": D.seen_test_strict}[s]
        r, pu, top = evaluate_scores(p, seen, F["_y"], D.num_courses)
        res[s] = {k: float(v) for k, v in r.items()}; probs[s] = p
        if s != "val":
            res[s + "_peruser"] = {k: v for k, v in pu.items()}; res[s + "_top10"] = top
    keras.backend.clear_session()
    return (res, probs) if return_probs else res


def _fit_aug(m, tr, va, ytr, yva, p_drop, epochs, batch, cbs, mon):
    """Sub-sequence cropping augmentation: each epoch every training example has its OLDEST k history items removed with
    probability p_drop (k uniform in 1..len-1).  Targets unchanged.  Keeps the 'last-item' structure intact."""
    rng = np.random.default_rng(0)
    X0, T0_, M0, C0 = tr["_X"], tr["tfeat"], tr["month"], tr["cand"]
    n_real = (X0 != 0).sum(1)
    cb = keras.callbacks.CallbackList(cbs, model=m)
    cb.on_train_begin()
    class H: history = {}
    H.history = {}
    for e in range(epochs):
        keep_k = np.where((rng.random(len(X0)) < p_drop) & (n_real > 1), rng.integers(1, np.maximum(n_real, 2)), 0)
        X, T = X0.copy(), T0_.copy()
        col = np.arange(L)[None, :]
        cut = col < (L - n_real + keep_k)[:, None]          # positions of dropped items (pre-padding)
        X[cut] = 0; T[cut] = 0
        cb.on_epoch_begin(e)
        h = m.fit([X, T, M0, C0], ytr, validation_data=(inputs_of(va), yva), epochs=1, batch_size=batch, shuffle=True, verbose=0)
        logs = {k: v[-1] for k, v in h.history.items()}
        for k, v in logs.items():
            H.history.setdefault(k, []).append(v)
        cb.on_epoch_end(e, logs)
        if m.stop_training:
            break
    cb.on_train_end()
    return H


# ----------------------------------------------------------------------------------------------- named variants (ablation factors)
VARIANTS = {
    "S0_base":      {},
    "T_gap":        {"time_seq": True},
    "C_calendar":   {"calendar": True},
    "P_candprior":  {"cand": True},
    "TC":           {"time_seq": True, "calendar": True},
    "TP":           {"time_seq": True, "cand": True},
    "CP":           {"calendar": True, "cand": True},
    "TCP":          {"time_seq": True, "calendar": True, "cand": True},
    "Q_trend": {"cand": True, "cand_cols": [0, 1]},                 # trending counts only (no launched/age flags)
    "Q4_trend_trans": {"cand": True, "cand_cols": [0, 1, 4]},       # + recent a->b transition counts
    "R_recenttrans":{"cand": True, "cand_cols": [4]},
    "P5_candprior_plus_trans": {"cand": True, "cand_cols": [0, 1, 2, 3, 4]},
    "TP5":          {"time_seq": True, "cand": True, "cand_cols": [0, 1, 2, 3, 4]},
    "LS01":         {"ls": 0.1},
    "AUX02":        {"aux": 0.2},
    "AUG03":        {"augment_p": 0.3},
}
