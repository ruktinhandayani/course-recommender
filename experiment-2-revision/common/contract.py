"""DATA CONTRACT: exact numbers the pipeline MUST reproduce (taken from the published artifacts in
course_recommender_artifacts_final/, verified 2026-10-03). Every experiment calls assert_contract() first."""
import ast, pickle
import pandas as pd
from .provenance import ARTIFACTS, md5, say
from pathlib import Path

RAW_MD5 = {  # raw data/ files used for the paper (data/interactions.csv is identical inside the project zip)
    "interactions.csv": "132de42fc9526715d335b4eb3b246500",
    "users.csv": "df26d20a3a07e17b165533648cc526eb",
    "courses.csv": "3ad82e313e81214e6ae89105a311f4a2",
    "course_alias_map.csv": "098ca854270cfa9a22d512fad49904b8",
}
EXPECT = {   # name: (expected, source)
    "courses in vocabulary": (60, "experiment_config.json num_courses_in_train_vocab"),
    "competencies": (27, "experiment_config.json"),
    "levels (incl. unknown)": (5, "encoder_mappings.pkl"),
    "train core rows": (35346, "data_split_summary_df.csv"),
    "train users": (4803, "data_split_summary_df.csv"),
    "validation samples": (4601, "data_split_summary_df / val_metadata.csv"),
    "test samples (default)": (4553, "evaluation_final.json test_samples"),
    "test samples (strict)": (4551, "observed; reproduces published strict metrics exactly"),
    "training sequences": (30543, "observed; saved model reproduces published metrics on it"),
    "certificate scaler max": (2.0, "certificate_count_scaler.pkl"),
}


def _row(ok, name, got, exp, src):
    say(f"  [{'PASS' if ok else 'FAIL'}] {name:28s} got={got!s:>14}  expected={exp!s:>14}   ({src})")
    return ok


def assert_contract(D, raw=True):
    """raw=True: also check raw-file md5s and that user sets equal the published metadata. Exits with code 2 on failure."""
    say("DATA CONTRACT check (published artifacts = ground truth)")
    ok = True
    got = {
        "courses in vocabulary": D.num_courses - 1, "competencies": D.num_competencies - 1, "levels (incl. unknown)": D.num_levels - 1,
        "train core rows": len(D.train_enc), "train users": D.train_enc["user_id"].nunique(), "validation samples": len(D.y_val),
        "test samples (default)": len(D.y_test), "test samples (strict)": len(D.y_test_strict),
        "training sequences": len(D.y_train), "certificate scaler max": float(D.scaler.data_max_[0]),
    }
    for k, (exp, src) in EXPECT.items():
        ok &= _row(got[k] == exp, k, got[k], exp, src)
    m = pickle.load(open(ARTIFACTS / "config/encoder_mappings.pkl", "rb"))
    ok &= _row(D.course_to_idx == {str(k): v for k, v in m["course_to_idx"].items()}, "course encoder identical", "-", "-", "encoder_mappings.pkl")
    ok &= _row(D.comp_to_idx == m["competency_to_idx"] and D.lvl_to_idx == m["level_to_idx"], "competency+level identical", "-", "-", "encoder_mappings.pkl")
    cat = pd.read_csv(ARTIFACTS / "tables/course_catalog.csv", dtype={"canonical_course_id": str})
    mine = D.train_enc.drop_duplicates("course_encoded")[["canonical_course_id", "certificate_count_train"]]
    c = cat.merge(mine, on="canonical_course_id", suffixes=("_p", "_m"))
    ok &= _row(len(c) == len(cat) and (c.certificate_count_train_p == c.certificate_count_train_m).all(), "certificate counts per course", "-", "-", "course_catalog.csv")
    if raw:
        for f, h in RAW_MD5.items():
            p = Path(D.data_dir) / f
            ok &= _row(p.exists() and md5(p) == h, f"md5 {f}", (md5(p)[:8] if p.exists() else "missing"), h[:8], "raw data fingerprint")
        for nm, meta in (("test", D.meta_test), ("val", D.meta_val)):
            pub = pd.read_csv(ARTIFACTS / f"tables/{nm}_metadata.csv", dtype={"user_id": str})
            same = list(pub["user_id"]) == list(meta["user_id"]) or set(pub["user_id"]) == set(meta["user_id"])
            ok &= _row(same, f"{nm} user set == published", len(meta), len(pub), f"{nm}_metadata.csv")
    if not ok:
        say("CONTRACT FAILED: the data/pipeline differs from the published run. STOP - do not trust any result.")
        raise SystemExit(2)
    say("CONTRACT OK: data and pipeline match the published run.")
