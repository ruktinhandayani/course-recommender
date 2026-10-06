from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from course_recommender.config import MlServiceSettings
from course_recommender.security import build_signature


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CRE ML API request headers.")
    parser.add_argument("path", help="Request path, e.g. /recommendations/export")
    parser.add_argument("--query", default="", help="Canonical query string without leading ?")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--request-id", default=f"manual-{int(time.time())}")
    parser.add_argument("--timestamp", default=str(int(time.time())))
    args = parser.parse_args()

    settings = MlServiceSettings()
    canonical_query = urlencode(sorted(parse_qsl(args.query, keep_blank_values=True)))
    signature = build_signature(
        method=args.method,
        path=args.path,
        query_string=canonical_query,
        timestamp=args.timestamp,
        request_id=args.request_id,
        secret=settings.hmac_secret,
    )

    if canonical_query:
        print(f"Canonical-Query: {canonical_query}")
    print(f"Authorization: Bearer {settings.api_key}")
    print(f"X-Request-Id: {args.request_id}")
    print(f"X-Timestamp: {args.timestamp}")
    print(f"X-Signature: {signature}")


if __name__ == "__main__":
    main()
