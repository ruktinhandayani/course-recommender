#!/usr/bin/env python3
"""
Step 2 of anonymization: apply the mapping built by generate_pseudonyms.py
to every raw file, writing de-identified copies into sibling *_anonymized/
directories. Raw files under data/ and course_recommender_artifacts_final/
are never modified in place.

What happens to each file:
  - users.csv            : full_name column DROPPED entirely; user_id replaced
  - interactions.csv      : user_id replaced, all other columns untouched
  - learning_progress_*   : user_id replaced, all other columns untouched
  - artifact tables with
    a user_id column      : user_id replaced, all other columns untouched
  - everything else under
    course_recommender_artifacts_final/ (model file, scalers, encoder
    mappings, config, non-user tables) : copied through unchanged — none of
    them carry a user_id or name.

Usage (after generate_pseudonyms.py has produced data_private/user_id_mapping.csv):
    python3 scripts/anonymize/apply_pseudonyms.py

Output:
    data_anonymized/...
    course_recommender_artifacts_final_anonymized/...
These *_anonymized/ trees are what you push to GitHub, never the raw
data/ or course_recommender_artifacts_final/ trees.
"""
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "course_recommender_artifacts_final"
PRIVATE_DIR = ROOT / "data_private"
MAPPING_PATH = PRIVATE_DIR / "user_id_mapping.csv"

DATA_OUT = ROOT / "data_anonymized"
ARTIFACTS_OUT = ROOT / "course_recommender_artifacts_final_anonymized"

FILES_DROP_FULL_NAME = {"users.csv"}

ARTIFACT_USER_ID_TABLES = {
    "similarity_ground_truth_result.csv",
    "softmax_ground_truth_result.csv",
    "test_metadata.csv",
    "val_metadata.csv",
    "test_seen_history_audit_df.csv",
    "val_seen_history_audit_df.csv",
}


def load_mapping() -> dict[str, str]:
    if not MAPPING_PATH.exists():
        print(
            f"ERROR: {MAPPING_PATH} not found. Run generate_pseudonyms.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    mapping = {}
    with MAPPING_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mapping[row["user_id"]] = row["pseudonym_code"]
    return mapping


def pseudonymize_csv(src: Path, dst: Path, mapping: dict[str, str], drop_full_name: bool) -> None:
    with src.open(newline="", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)
        fieldnames = [c for c in reader.fieldnames if not (drop_full_name and c == "full_name")]
        rows = []
        unmapped = 0
        for row in reader:
            if "user_id" in row:
                uid = row["user_id"]
                if uid in mapping:
                    row["user_id"] = mapping[uid]
                elif uid:
                    unmapped += 1
            if drop_full_name:
                row.pop("full_name", None)
            rows.append(row)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    note = f" ({unmapped} unmapped user_id left as-is!)" if unmapped else ""
    print(f"  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}{note}")


def main() -> int:
    mapping = load_mapping()
    print(f"Loaded {len(mapping)} pseudonym mappings.\n")

    print("Processing data/ ...")
    for src in sorted(DATA_DIR.glob("*.csv")):
        dst = DATA_OUT / src.name
        pseudonymize_csv(src, dst, mapping, drop_full_name=src.name in FILES_DROP_FULL_NAME)

    print("\nProcessing course_recommender_artifacts_final/ ...")
    for src in sorted(ARTIFACTS_DIR.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(ARTIFACTS_DIR)
        dst = ARTIFACTS_OUT / rel
        if src.suffix == ".csv" and src.name in ARTIFACT_USER_ID_TABLES:
            pseudonymize_csv(src, dst, mapping, drop_full_name=False)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)} (copied, no user_id)")

    print(f"\nDone. Anonymized trees written to:\n  {DATA_OUT}\n  {ARTIFACTS_OUT}")
    print("Next: run verify_anonymization.py before pushing anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
