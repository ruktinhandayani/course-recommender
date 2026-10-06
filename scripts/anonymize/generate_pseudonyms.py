#!/usr/bin/env python3
"""
Step 1 of anonymization: build a deterministic, salted pseudonym mapping for
every user_id found in the raw data files.

Pseudonym = "U-" + first 10 hex chars of HMAC-SHA256(salt, user_id)
  - Deterministic: the same user_id always maps to the same code, so joins
    across interactions.csv / users.csv / learning_progress_*.csv / artifact
    tables stay consistent.
  - Irreversible without the salt: without CRE_ML_ANON_SALT, the mapping
    cannot be inverted back to the original user_id.
  - 40 bits of hash space for ~9,600 users keeps collision probability
    negligible (~1e-6); the script hard-aborts on any collision so you never
    silently ship a broken mapping.

user_id is read and written as a zero-padded STRING throughout — never cast
to int — because identifier_integrity_df.csv already documents that these
IDs carry meaningful leading zeros.

Usage:
    export CRE_ML_ANON_SALT=$(openssl rand -hex 32)   # generate once, keep secret
    python3 scripts/anonymize/generate_pseudonyms.py

Output:
    data_private/user_id_mapping.csv   (original_user_id -> pseudonym_code)
    This file is the ONLY place the original IDs and their codes are linked.
    It must stay out of git (see .gitignore) and off GitHub. Keep it
    somewhere safe in case you ever need to re-link a result internally.
"""
import csv
import hashlib
import hmac
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACT_TABLES_DIR = ROOT / "course_recommender_artifacts_final" / "tables"
PRIVATE_DIR = ROOT / "data_private"
MAPPING_PATH = PRIVATE_DIR / "user_id_mapping.csv"

SOURCE_FILES = [
    DATA_DIR / "users.csv",
    DATA_DIR / "interactions.csv",
    DATA_DIR / "learning_progress_detail.csv",
    DATA_DIR / "learning_progress_summary.csv",
]

# Artifact tables that carry a user_id column (confirmed by header scan).
ARTIFACT_USER_ID_TABLES = [
    "similarity_ground_truth_result.csv",
    "softmax_ground_truth_result.csv",
    "test_metadata.csv",
    "val_metadata.csv",
    "test_seen_history_audit_df.csv",
    "val_seen_history_audit_df.csv",
]


def read_user_ids(path: Path) -> set[str]:
    if not path.exists():
        print(f"  [skip] {path} not found")
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "user_id" not in (reader.fieldnames or []):
            print(f"  [skip] {path.name} has no user_id column")
            return set()
        return {row["user_id"] for row in reader if row["user_id"]}


def main() -> int:
    salt = os.environ.get("CRE_ML_ANON_SALT")
    if not salt:
        print(
            "ERROR: CRE_ML_ANON_SALT is not set.\n"
            "Generate one ONCE and keep it secret (never commit it):\n"
            "  export CRE_ML_ANON_SALT=$(openssl rand -hex 32)\n"
            "Then re-run this script. Save the salt somewhere safe (e.g. a\n"
            "password manager) — losing it means you can no longer verify\n"
            "old pseudonyms, and reusing a DIFFERENT salt later will produce\n"
            "DIFFERENT codes for the same people.",
            file=sys.stderr,
        )
        return 1

    print("Scanning raw files for user_id values...")
    all_ids: set[str] = set()
    for path in SOURCE_FILES:
        ids = read_user_ids(path)
        print(f"  {path.name}: {len(ids)} unique user_id(s)")
        all_ids |= ids
    for name in ARTIFACT_USER_ID_TABLES:
        path = ARTIFACT_TABLES_DIR / name
        ids = read_user_ids(path)
        print(f"  tables/{name}: {len(ids)} unique user_id(s)")
        all_ids |= ids

    if not all_ids:
        print("ERROR: no user_id values found anywhere. Check paths.", file=sys.stderr)
        return 1

    print(f"\nTotal unique user_id across all files: {len(all_ids)}")

    salt_bytes = bytes.fromhex(salt) if _looks_hex(salt) else salt.encode("utf-8")

    mapping: dict[str, str] = {}
    codes_seen: set[str] = set()
    for uid in sorted(all_ids):
        digest = hmac.new(salt_bytes, uid.encode("utf-8"), hashlib.sha256).hexdigest()
        code = "U-" + digest[:10]
        if code in codes_seen:
            print(
                f"ERROR: collision detected for pseudonym {code} "
                f"(user_id={uid}). Increase the hex-digit length in this "
                f"script and re-run.",
                file=sys.stderr,
            )
            return 1
        codes_seen.add(code)
        mapping[uid] = code

    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    with MAPPING_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "pseudonym_code"])
        for uid, code in mapping.items():
            writer.writerow([uid, code])

    print(f"\nWrote mapping for {len(mapping)} users to {MAPPING_PATH}")
    print("This file is PRIVATE. Confirm it is covered by .gitignore before")
    print("doing anything else, then run apply_pseudonyms.py next.")
    return 0


def _looks_hex(s: str) -> bool:
    try:
        int(s, 16)
        return len(s) % 2 == 0
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
