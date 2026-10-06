"""Bearer-token and HMAC validation for the CRE ML API."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from fastapi import Request

from .config import MlServiceSettings


EMPTY_BODY_SHA256 = hashlib.sha256(b"").hexdigest()


def canonical_query_string(request: Request) -> str:
    pairs = sorted(request.query_params.multi_items())
    return urlencode(pairs, doseq=True)


def canonical_string(request: Request, timestamp: str, request_id: str) -> str:
    return "\n".join(
        [
            request.method.upper(),
            request.url.path,
            canonical_query_string(request),
            EMPTY_BODY_SHA256,
            timestamp,
            request_id,
        ]
    )


def build_signature(
    method: str,
    path: str,
    query_string: str,
    timestamp: str,
    request_id: str,
    secret: str,
) -> str:
    payload = "\n".join(
        [
            method.upper(),
            path,
            query_string,
            EMPTY_BODY_SHA256,
            timestamp,
            request_id,
        ]
    )
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_request_security(request: Request, settings: MlServiceSettings) -> tuple[bool, int, str, str]:
    """Return (ok, http_status, error_code, message)."""
    if not settings.require_auth:
        return True, 200, "", ""

    if not settings.api_key or not settings.hmac_secret:
        return False, 503, "AUTH_NOT_CONFIGURED", "API authentication is not configured."

    authorization = request.headers.get("authorization", "")
    request_id = request.headers.get("x-request-id", "")
    timestamp = request.headers.get("x-timestamp", "")
    signature = request.headers.get("x-signature", "")

    if not authorization.startswith("Bearer "):
        return False, 401, "INVALID_API_KEY", "Missing bearer API key."

    supplied_key = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied_key, settings.api_key):
        return False, 401, "INVALID_API_KEY", "API key is invalid."

    if not request_id:
        return False, 400, "MISSING_REQUEST_ID", "X-Request-Id header is required."

    if not timestamp:
        return False, 403, "EXPIRED_TIMESTAMP", "X-Timestamp header is required."

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False, 403, "EXPIRED_TIMESTAMP", "X-Timestamp must be a Unix timestamp."

    now = int(time.time())
    if abs(now - timestamp_int) > settings.timestamp_tolerance_seconds:
        return False, 403, "EXPIRED_TIMESTAMP", "Request timestamp is outside the allowed window."

    if not signature:
        return False, 403, "INVALID_SIGNATURE", "X-Signature header is required."

    expected = hmac.new(
        settings.hmac_secret.encode("utf-8"),
        canonical_string(request, timestamp, request_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return False, 403, "INVALID_SIGNATURE", "Request signature is invalid."

    return True, 200, "", ""
