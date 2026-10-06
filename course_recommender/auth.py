"""Small admin-session helpers for the standalone ML console."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Request

from .config import MlServiceSettings


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected_hex = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, f"{algorithm}${salt}${expected_hex}")


def validate_admin_credentials(username: str, password: str, settings: MlServiceSettings) -> bool:
    if not hmac.compare_digest(username, settings.admin_username):
        return False
    if settings.admin_password_hash:
        return verify_password(password, settings.admin_password_hash)
    if not settings.admin_password:
        return False
    return hmac.compare_digest(password, settings.admin_password)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token(settings: MlServiceSettings) -> str:
    if not settings.session_secret:
        raise ValueError("CRE_ML_SESSION_SECRET must be configured.")
    now = int(time.time())
    payload = {
        "sub": settings.admin_username,
        "iat": now,
        "exp": now + int(settings.session_max_age_seconds),
        "nonce": secrets.token_hex(12),
    }
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded_payload}.{_sign(encoded_payload, settings.session_secret)}"


def read_session_token(token: str, settings: MlServiceSettings) -> dict[str, Any] | None:
    if not settings.session_secret:
        return None
    try:
        encoded_payload, supplied_signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign(encoded_payload, settings.session_secret)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None

    try:
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    except Exception:
        return None

    if payload.get("sub") != settings.admin_username:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def request_has_admin_session(request: Request, settings: MlServiceSettings) -> bool:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return False
    return read_session_token(token, settings) is not None
