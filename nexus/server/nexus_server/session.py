"""One browser-session cookie. No expiry, renewal, or accounts."""

from __future__ import annotations

import hashlib
import hmac
from typing import Mapping

COOKIE_NAME = "nexus_session"
_PAYLOAD = b"ok"


def sign_session(secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), _PAYLOAD, hashlib.sha256).hexdigest()
    return f"ok.{digest}"


def session_cookie_ok(value: str | None, secret: str) -> bool:
    if not value or not secret:
        return False
    payload, separator, digest = value.partition(".")
    if separator != "." or payload != "ok":
        return False
    expected = hmac.new(secret.encode("utf-8"), _PAYLOAD, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def cookie_from_header(header: str | None, secret: str) -> bool:
    if not header:
        return False
    for part in header.split(";"):
        name, separator, value = part.strip().partition("=")
        if separator == "=" and name == COOKIE_NAME:
            return session_cookie_ok(value, secret)
    return False


def scope_has_session(scope: Mapping[str, object], secret: str) -> bool:
    for key, value in scope.get("headers") or []:
        if key == b"cookie":
            raw = value.decode("latin-1") if isinstance(value, (bytes, bytearray)) else str(value)
            return cookie_from_header(raw, secret)
    return False
