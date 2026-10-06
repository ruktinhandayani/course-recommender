"""Generate a PBKDF2 admin password hash for CRE_ML_ADMIN_PASSWORD_HASH."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from course_recommender.auth import hash_password  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a CRE admin password hash.")
    parser.add_argument("--password", help="Password to hash. Omit to prompt securely.")
    args = parser.parse_args()

    password = args.password
    if password is None:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            raise SystemExit("Passwords do not match.")

    if len(password) < 16:
        raise SystemExit("Use an admin password with at least 16 characters.")

    print(hash_password(password))


if __name__ == "__main__":
    main()
