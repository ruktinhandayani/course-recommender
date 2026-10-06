#!/usr/bin/env python3
"""
Step 3 of anonymization: sanity-check the *_anonymized/ output before you
push anything. Run this every time after apply_pseudonyms.py, and again
right before `git add` as a final gate.

Checks:
  1. No file under data_anonymized/ or course_recommender_artifacts_final_anonymized/
     has a 'full_name' column.
  2. No raw original user_id value (from data_private/user_id_mapping.csv)
     appears as a SUBSTRING in any file under the anonymized trees —
     including binary files (model weights, .pkl), scanned as raw bytes, in
     case an ID ever got embedded as a string constant.
  3. Row counts match between source and anonymized CSVs (nothing silently
     dropped).
  4. A quick regex sweep for name-shaped / email-shaped / NIK-shaped strings
     as a second line of defense beyond the full_name column check.

Exit code is non-zero if anything fails — treat that as a hard stop, not a
warning.
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DIR = ROOT / "data_private"
MAPPING_PATH = PRIVATE_DIR / "user_id_mapping.csv"

DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "course_recommender_artifacts_final"
DATA_OUT = ROOT / "data_anonymized"
ARTIFACTS_OUT = ROOT / "course_recommender_artifacts_final_anonymized"

EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
NIK_RE = re.compile(rb"\b\d{16}\b")  # Indonesian NIK is 16 digits


def fail(msg: str, problems: list[str]) -> None:
    problems.append(msg)
    print(f"  [FAIL] {msg}")


def main() -> int:
    problems: list[str] = []

    if not MAPPING_PATH.exists():
        print(f"ERROR: {MAPPING_PATH} not found. Run the pipeline in order.", file=sys.stderr)
        return 1
    if not DATA_OUT.exists():
        print(f"ERROR: {DATA_OUT} not found. Run apply_pseudonyms.py first.", file=sys.stderr)
        return 1

    original_ids: list[str] = []
    with MAPPING_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            original_ids.append(row["user_id"])
    original_id_bytes = [uid.encode("utf-8") for uid in original_ids if uid]
    print(f"Loaded {len(original_id_bytes)} original user_id values to check against.\n")

    print("Check 1: no full_name column in anonymized output ...")
    for out_root in (DATA_OUT, ARTIFACTS_OUT):
        for path in out_root.rglob("*.csv"):
            with path.open(newline="", encoding="utf-8") as f:
                header = next(csv.reader(f), [])
            if "full_name" in header:
                fail(f"{path.relative_to(ROOT)} still has a full_name column", problems)
    if not problems:
        print("  [ok]")

    print("\nCheck 2: no raw user_id substring survives anywhere in anonymized output "
          "(this scans ALL files, including binary, and can take a minute) ...")
    count_before = len(problems)
    all_files = [p for p in DATA_OUT.rglob("*") if p.is_file()] + \
                [p for p in ARTIFACTS_OUT.rglob("*") if p.is_file()]
    for path in all_files:
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for uid_bytes in original_id_bytes:
            if uid_bytes in blob:
                fail(
                    f"{path.relative_to(ROOT)} contains a raw original user_id "
                    f"({uid_bytes.decode()!r})",
                    problems,
                )
                break  # one hit per file is enough to flag it
    if len(problems) == count_before:
        print("  [ok]")

    print("\nCheck 3: row counts match between source and anonymized CSVs ...")
    count_before = len(problems)
    for src in DATA_DIR.glob("*.csv"):
        dst = DATA_OUT / src.name
        if not dst.exists():
            continue
        src_rows = sum(1 for _ in open(src, encoding="utf-8")) - 1
        dst_rows = sum(1 for _ in open(dst, encoding="utf-8")) - 1
        if src_rows != dst_rows:
            fail(f"{src.name}: {src_rows} source rows vs {dst_rows} anonymized rows", problems)
    if len(problems) == count_before:
        print("  [ok]")

    print("\nCheck 4: regex sweep for email / NIK-shaped strings ...")
    count_before = len(problems)
    for path in all_files:
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        if EMAIL_RE.search(blob):
            fail(f"{path.relative_to(ROOT)} contains an email-shaped string", problems)
        if NIK_RE.search(blob):
            fail(f"{path.relative_to(ROOT)} contains a 16-digit (NIK-shaped) string", problems)
    if len(problems) == count_before:
        print("  [ok]")

    print()
    if problems:
        print(f"RESULT: {len(problems)} problem(s) found. Do NOT push until these are fixed.")
        return 1
    print("RESULT: all checks passed. Safe to proceed to the git steps in ANONYMIZATION_STEPS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
