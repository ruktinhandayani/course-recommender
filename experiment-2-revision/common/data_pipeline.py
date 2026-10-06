"""Data pipeline ported 1:1 from notebooks/research/Course_Recommender_Revised_Academic_Markdown.ipynb
(cells 4-38). Same cleaning, noise filtering, temporal split, train-only encoders, sequence building.

DATA RULES (see DATA_CONTRACT.md; enforced by common/contract.py):
  * IDs are read as text (dtype=str) so leading zeros survive.
  * User-course pairs made only of the 291 legacy `certified` rows (no enrollment) are dropped.
  * Masking protocol = full_pre_target_history: D.seen[...] masks EVERY course in the user's whole history.
  * Default data dir is the RAW local folder `data` (override with env DATA_DIR). Raw data never leaves this machine.

Usage:
    from common.data_pipeline import build_dataset
    D = build_dataset()            # reads DATA_DIR env var, default "data"
"""
import os
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

MAX_SEQ_LEN = 10
MIN_USER_HISTORY_FOR_SPLIT = 4
MIN_COURSE_COUNT_TRAIN = 20
UNKNOWN_TOKEN = "__UNKNOWN__"


# ---------------------------------------------------------------- helpers (cell 6)
def _clean_columns(df):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.lower()
    return df


def _clean_id(s):
    s = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return s.replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})


def _clean_text(s):
    s = s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    return s.replace({"nan": np.nan, "none": np.nan, "None": np.nan, "": np.nan})


def pad_pre(seqs, dtype="int32", maxlen=MAX_SEQ_LEN):
    """Equivalent of keras pad_sequences(padding='pre', truncating='pre') without the TF import."""
    out = np.zeros((len(seqs), maxlen), dtype=dtype)
    for i, s in enumerate(seqs):
        s = list(s)[-maxlen:]
        if s:
            out[i, -len(s):] = s
    return out


# ---------------------------------------------------------------- noise cleaning (cell 14)
def _norm_noise(v):
    if pd.isna(v):
        return ""
    t = str(v).lower().strip()
    t = t.replace("“", '"').replace("”", '"').replace("’", "'")
    t = re.sub(r"[_\-/]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_NOISE_NAME = {
    "uji coba / coba course": [r"\buji\s*coba\b", r"^coba$", r"\bcoba\s+course\b", r"\bcourse\s+coba\b"],
    "generic test course/material": [
        r"^test(?:\s+\d+[a-z]?|\s+scorm|\s+ssl|\s+course|\s+for\s+remedial|\s+doc\s+uat|\s+uat|\s*[-:]|$)",
        r"^materi\s+test\b", r"^materi\s+course\s+test\b", r"^mcl\s+test\b",
        r"\btest\s*&\s*pilot\s+course\b", r"\bdoc\s+uat\b", r"\buat\b"],
    "dummy/sandbox/internal testing": [r"\bdummy\b", r"\bsandbox\b", r"\binternal\s+test\b", r"\btesting\s+course\b"],
}
_NOISE_KEEP = [r"\bnon\s+dis?tructive\s+test\b", r"\bstress\s+management\b", r"\btrial\s+balance\b",
               r"\bparameter\s+uji\b", r"\bpengujian\b", r"\bdevelopment\b"]
_NOISE_DESC = {"description states testing only": [r"\bhanya\s+uji\s*coba\b", r"\bstress\s*test\b", r"\bfor\s+testing\s+only\b"]}


def _noise_reason(row):
    name = _norm_noise(row.get("course_name", ""))
    desc = _norm_noise(row.get("description", ""))
    combined = f"{name} {desc}".strip()
    if any(re.search(p, name) for p in _NOISE_KEEP):
        return ""
    reasons = []
    for r, pats in _NOISE_NAME.items():
        if any(re.search(p, name) for p in pats):
            reasons.append(r)
    for r, pats in _NOISE_DESC.items():
        if any(re.search(p, combined) for p in pats):
            reasons.append(r)
    return "; ".join(dict.fromkeys(reasons))


# ---------------------------------------------------------------- holdout builder (cell 36)
def _make_holdout(history_df, target_df, label):
    hist = history_df.groupby("user_id").agg({
        "course_encoded": list, "competency_encoded": list, "level_encoded": list,
        "course_has_certificate_train": list, "certificate_count_scaled": list}).reset_index()
    merged = target_df.merge(hist, on="user_id", how="inner", suffixes=("_target", "_history"))
    Xc, Xk, Xl, Xf, Xn, y, meta = [], [], [], [], [], [], []
    for _, r in merged.iterrows():
        h = r["course_encoded_history"]
        if len(h) < 2:
            continue
        Xc.append(h); Xk.append(r["competency_encoded_history"]); Xl.append(r["level_encoded_history"])
        Xf.append(r["course_has_certificate_train_history"]); Xn.append(r["certificate_count_scaled_history"])
        y.append(r["course_encoded_target"])
        meta.append({"user_id": r["user_id"], "seen_full": sorted(set(int(x) for x in h)), "ground_truth_encoded": r["course_encoded_target"],
                     "ground_truth_course": r["course_name"], "sequence_length": len(h), "dataset": label})
    X = [pad_pre(Xc), pad_pre(Xk), pad_pre(Xl),
         pad_pre(Xf, "float32")[..., None], pad_pre(Xn, "float32")[..., None]]
    return X, np.array(y).astype(int), pd.DataFrame(meta)


def seen_matrix(meta, num_courses):
    """Boolean (n_users, num_courses): every course in the user's FULL pre-target history (not only the last 10)."""
    M = np.zeros((len(meta), num_courses), dtype=bool)
    for k, seen in enumerate(meta["seen_full"]):
        M[k, seen] = True
    return M


# ---------------------------------------------------------------- main entry
def build_dataset(data_dir=None, min_course_count=MIN_COURSE_COUNT_TRAIN, verbose=True, force_course_ids=None):
    """force_course_ids: optional list of canonical course ids that replaces the count-based vocabulary
    (used only by E0 to reproduce the published 60-course vocabulary)."""
    data_dir = Path(data_dir or os.getenv("DATA_DIR", "data")).expanduser()
    if not data_dir.is_absolute():                      # relative paths are ALWAYS relative to the project root,
        data_dir = Path(__file__).resolve().parents[2] / data_dir   # never to the current directory
    data_dir = data_dir.resolve()
    rd = lambda f: pd.read_csv(data_dir / f, dtype=str)  # keep leading zeros in IDs (published run did)
    interactions, courses, users, alias_map = (_clean_columns(rd(f)) for f in
        ("interactions.csv", "courses.csv", "users.csv", "course_alias_map.csv"))

    # cell 6
    if "interaction_id" not in interactions.columns:
        interactions["interaction_id"] = np.arange(1, len(interactions) + 1)
    interactions["interaction_id"] = _clean_id(interactions["interaction_id"])
    interactions["user_id"] = _clean_id(interactions["user_id"])
    interactions["course_id"] = _clean_id(interactions["course_id"])
    interactions["interaction_type"] = _clean_text(interactions["interaction_type"]).str.lower()
    if "source_system" in interactions.columns:
        interactions["source_system"] = _clean_text(interactions["source_system"])
    else:
        interactions["source_system"] = "unknown"
    users["user_id"] = _clean_id(users["user_id"])
    users["full_name"] = _clean_text(users["full_name"]) if "full_name" in users.columns else "Unknown"
    courses["canonical_course_id"] = _clean_id(courses["canonical_course_id"])
    courses["course_name"] = _clean_text(courses["course_name"])
    courses["description"] = _clean_text(courses["description"]) if "description" in courses.columns else "Not Available"
    courses["level"] = _clean_text(courses["level"]) if "level" in courses.columns else "Not Available"
    if "kompetensi" in courses.columns:
        courses["kompetensi"] = _clean_text(courses["kompetensi"])
    elif "competency" in courses.columns:
        courses["kompetensi"] = _clean_text(courses["competency"])
    else:
        courses["kompetensi"] = "Not Available"
    alias_map["legacy_course_id"] = _clean_id(alias_map["legacy_course_id"])
    alias_map["canonical_course_id"] = _clean_id(alias_map["canonical_course_id"])
    interactions = interactions.dropna(subset=["user_id", "course_id"])
    courses = courses.dropna(subset=["canonical_course_id", "course_name"])
    users = users.dropna(subset=["user_id"])
    alias_map = alias_map.dropna(subset=["legacy_course_id", "canonical_course_id"])
    interactions = interactions.drop_duplicates()
    courses = courses.drop_duplicates(subset=["canonical_course_id"])
    users = users.drop_duplicates(subset=["user_id"])
    alias_map = alias_map.drop_duplicates(subset=["legacy_course_id"])

    # cell 8
    interactions["_row_order"] = np.arange(len(interactions))
    interactions["event_timestamp"] = pd.to_datetime(interactions["event_timestamp"], errors="coerce") \
        if "event_timestamp" in interactions.columns else pd.NaT
    am = alias_map.rename(columns={"canonical_course_id": "mapped_canonical_course_id"})
    im = interactions.merge(am, left_on="course_id", right_on="legacy_course_id", how="left")
    im["canonical_course_id"] = im["mapped_canonical_course_id"].fillna(im["course_id"])

    # cell 12
    cert_kw = ["cert", "certificate", "certified", "sertifikat", "bersertifikat", "passed", "pass", "lulus"]
    enr_kw = ["enroll", "enrolled", "enrollment", "ambil", "mengambil"]
    has = lambda t, kws: any(k in str(t).lower() for k in kws)
    im["is_certificate"] = im["interaction_type"].apply(lambda x: int(has(x, cert_kw)))
    im["is_enrolled"] = im["interaction_type"].apply(lambda x: int(has(x, enr_kw)))

    # cell 14 (Course senin decision = keep; manual list empty)
    audit = courses.copy()
    audit["noise_reason"] = audit.apply(_noise_reason, axis=1)
    noise_ids = set(audit.loc[audit["noise_reason"].ne(""), "canonical_course_id"].astype(str))
    courses = audit[audit["noise_reason"].eq("")].drop(columns=["noise_reason"]).reset_index(drop=True)

    # cell 16
    raw = im.merge(courses, on="canonical_course_id", how="left")
    raw = raw.merge(users[["user_id", "full_name"]], on="user_id", how="left")
    for c in ("course_name", "description", "level", "kompetensi"):
        raw[c] = raw[c].fillna("Not Available")

    # cell 18
    def smin_dt(x):
        x = x.dropna()
        return x.min() if len(x) else pd.NaT

    def smin_num(x):
        x = pd.to_numeric(x, errors="coerce").dropna()
        return x.min() if len(x) else np.nan

    ucb = raw.groupby(["user_id", "canonical_course_id"], as_index=False).agg(
        course_name=("course_name", "first"), description=("description", "first"),
        level=("level", "first"), kompetensi=("kompetensi", "first"),
        first_event_timestamp=("event_timestamp", smin_dt),
        first_interaction_id=("interaction_id", smin_num), first_row_order=("_row_order", "min"),
        enrolled_available_raw=("is_enrolled", "max"), certificate_available_raw=("is_certificate", "max"))
    # E0 finding: the published run only kept user-course pairs with an enrollment; pairs made only of the 291
    # legacy 'certified' rows (no timestamp) are excluded. Certified rows next to an enrollment still count.
    ucb = ucb[ucb["enrolled_available_raw"] == 1].copy()
    ucb["sort_timestamp"] = ucb["first_event_timestamp"]
    ucb["sort_interaction_id"] = ucb["first_interaction_id"].fillna(999999999)
    ucb["sort_row_order"] = ucb["first_row_order"]
    sort_cols = ["user_id", "sort_timestamp", "sort_interaction_id", "sort_row_order"]
    ucb = ucb.sort_values(sort_cols).reset_index(drop=True)

    # cell 20
    base = ucb[(ucb["course_name"] != "Not Available") & (ucb["kompetensi"] != "Not Available")].copy()
    cnt = base.groupby("user_id")["canonical_course_id"].count()
    base = base[base["user_id"].isin(cnt[cnt >= MIN_USER_HISTORY_FOR_SPLIT].index)].copy()
    base = base.sort_values(sort_cols).reset_index(drop=True)

    # cell 22: temporal split
    tc, vt, ph, tt = [], [], [], []
    for _, g in base.groupby("user_id"):
        g = g.sort_values(["sort_timestamp", "sort_interaction_id", "sort_row_order"])
        if len(g) >= 4:
            tt.append(g.iloc[-1]); ph.append(g.iloc[:-1]); vt.append(g.iloc[-2]); tc.append(g.iloc[:-2])
    train_core_raw = pd.concat(tc).reset_index(drop=True)
    val_target_raw = pd.DataFrame(vt).reset_index(drop=True)
    pretest_raw = pd.concat(ph).reset_index(drop=True)
    test_target_raw = pd.DataFrame(tt).reset_index(drop=True)

    # cell 24
    cc = train_core_raw["canonical_course_id"].value_counts()
    valid = cc[cc >= min_course_count].index
    if force_course_ids is not None:
        valid = pd.Index([str(c) for c in force_course_ids])
    flt = lambda d: d[d["canonical_course_id"].isin(valid)].copy()
    train_core, val_target, pretest, test_target = map(flt, (train_core_raw, val_target_raw, pretest_raw, test_target_raw))
    n_tc = train_core.groupby("user_id")["canonical_course_id"].count()
    val_target = val_target[val_target["user_id"].isin(n_tc[n_tc >= 2].index)].copy()
    n_pt = pretest.groupby("user_id")["canonical_course_id"].count()
    test_target = test_target[test_target["user_id"].isin(n_pt[n_pt >= 2].index)].copy()

    # cell 26: train-only certificate features
    cert = train_core.groupby("canonical_course_id", as_index=False).agg(
        certificate_count_train=("certificate_available_raw", "sum"))
    cert["course_has_certificate_train"] = np.where(cert["certificate_count_train"] > 0, 1, 0)

    def add_cert(df):
        df = df.drop(columns=["certificate_count", "course_has_certificate", "certificate_count_train",
                              "course_has_certificate_train"], errors="ignore")
        df = df.merge(cert, on="canonical_course_id", how="left")
        df["certificate_count_train"] = df["certificate_count_train"].fillna(0)
        df["course_has_certificate_train"] = df["course_has_certificate_train"].fillna(0).astype(int)
        return df

    train_core, val_target, pretest, test_target = map(add_cert, (train_core, val_target, pretest, test_target))

    # cell 30: train-only encoders and scaler
    course_to_idx = {c: i + 1 for i, c in enumerate(sorted(train_core["canonical_course_id"].astype(str).unique()))}
    comps = sorted(train_core["kompetensi"].astype(str).unique().tolist())
    if UNKNOWN_TOKEN not in comps:
        comps.append(UNKNOWN_TOKEN)
    comp_to_idx = {v: i + 1 for i, v in enumerate(comps)}
    lvls = sorted(train_core["level"].astype(str).unique().tolist())
    if UNKNOWN_TOKEN not in lvls:
        lvls.append(UNKNOWN_TOKEN)
    lvl_to_idx = {v: i + 1 for i, v in enumerate(lvls)}
    scaler = MinMaxScaler().fit(train_core[["certificate_count_train"]])

    def enc(df):
        df = df.copy()
        for c in ("canonical_course_id", "kompetensi", "level"):
            df[c] = df[c].astype(str)
        df["course_encoded"] = df["canonical_course_id"].map(course_to_idx)
        df["competency_clean"] = df["kompetensi"].where(df["kompetensi"].isin(comp_to_idx.keys()), UNKNOWN_TOKEN)
        df["level_clean"] = df["level"].where(df["level"].isin(lvl_to_idx.keys()), UNKNOWN_TOKEN)
        df["competency_encoded"] = df["competency_clean"].map(comp_to_idx)
        df["level_encoded"] = df["level_clean"].map(lvl_to_idx)
        df = df.dropna(subset=["course_encoded", "competency_encoded", "level_encoded"])
        for c in ("course_encoded", "competency_encoded", "level_encoded"):
            df[c] = df[c].astype(int)
        df[["certificate_count_scaled"]] = scaler.transform(df[["certificate_count_train"]])
        return df

    train_enc, val_enc, pre_enc, test_enc = map(enc, (train_core, val_target, pretest, test_target))
    num_courses, num_comp, num_lvl = len(course_to_idx) + 1, len(comp_to_idx) + 1, len(lvl_to_idx) + 1

    # cell 34: training sequences (every prefix -> next course)
    ts = train_enc.groupby("user_id").agg({
        "course_encoded": list, "competency_encoded": list, "level_encoded": list,
        "course_has_certificate_train": list, "certificate_count_scaled": list}).reset_index()
    Xc, Xk, Xl, Xf, Xn, ytr = [], [], [], [], [], []
    for _, r in ts.iterrows():
        c = r["course_encoded"]
        for i in range(1, len(c)):
            Xc.append(c[:i]); Xk.append(r["competency_encoded"][:i]); Xl.append(r["level_encoded"][:i])
            Xf.append(r["course_has_certificate_train"][:i]); Xn.append(r["certificate_count_scaled"][:i])
            ytr.append(c[i])
    X_train = [pad_pre(Xc), pad_pre(Xk), pad_pre(Xl), pad_pre(Xf, "float32")[..., None], pad_pre(Xn, "float32")[..., None]]
    y_train = np.array(ytr)

    # cells 38 / 80
    X_val, y_val, meta_val = _make_holdout(train_enc, val_enc, "validation")
    X_test, y_test, meta_test = _make_holdout(pre_enc, test_enc, "test")
    X_test_strict, y_test_strict, meta_test_strict = _make_holdout(train_enc, test_enc, "strict_train_history_test")

    D = SimpleNamespace(
        data_dir=str(data_dir), num_courses=num_courses, num_competencies=num_comp, num_levels=num_lvl,
        course_to_idx=course_to_idx, comp_to_idx=comp_to_idx, lvl_to_idx=lvl_to_idx, scaler=scaler,
        train_enc=train_enc, val_enc=val_enc, pretest_enc=pre_enc, test_enc=test_enc,
        X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val, meta_val=meta_val,
        X_test=X_test, y_test=y_test, meta_test=meta_test,
        X_test_strict=X_test_strict, y_test_strict=y_test_strict, meta_test_strict=meta_test_strict,
        n_noise_courses_removed=len(noise_ids))
    D.seen_val, D.seen_test, D.seen_test_strict = (seen_matrix(m, num_courses) for m in (meta_val, meta_test, meta_test_strict))
    D.splits = {"default": (X_test, y_test, meta_test), "strict": (X_test_strict, y_test_strict, meta_test_strict)}
    D.seen = {"default": D.seen_test, "strict": D.seen_test_strict}
    if verbose:
        print(f"[data] {data_dir.name}: courses={num_courses-1} comps={num_comp-1} levels={num_lvl-1} "
              f"train_seq={len(y_train)} val={len(y_val)} test={len(y_test)} strict={len(y_test_strict)} "
              f"noise_removed={len(noise_ids)}")
    return D
