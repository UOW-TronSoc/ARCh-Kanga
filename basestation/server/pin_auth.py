"""PIN-based auth: hash stored in a file, verified with Django-compatible PBKDF2."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_DEFAULT_PIN_FILE = _BASE / "data" / ".pin_hash"
PIN_FILE = Path(os.environ.get("BASESTATION_PIN_HASH_FILE", _DEFAULT_PIN_FILE))


def _read_file_hash() -> str | None:
    if PIN_FILE.is_file():
        try:
            return PIN_FILE.read_text(encoding="utf-8").strip() or None
        except OSError:
            pass
    return None


def _write_file_hash(hash_val: str) -> None:
    PIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIN_FILE.write_text(hash_val, encoding="utf-8")
    os.chmod(PIN_FILE, 0o600)


def is_pin_configured() -> bool:
    return _read_file_hash() is not None


def _make_password(password: str) -> str:
    """Same format as Django's make_password (pbkdf2_sha256)."""
    salt = secrets.token_hex(12)
    iterations = 720000
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    hash_b64 = base64.b64encode(digest).decode("ascii").strip()
    return f"pbkdf2_sha256${iterations}${salt}${hash_b64}"


def _check_password(password: str, encoded: str) -> bool:
    try:
        _algo, iterations_str, salt, hash_b64 = encoded.split("$", 3)
        iterations = int(iterations_str)
        expected = base64.b64decode(hash_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        )
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def set_pin_hash(pin: str) -> None:
    if len(pin) != 6 or not pin.isdigit():
        raise ValueError("PIN must be exactly 6 digits")
    _write_file_hash(_make_password(pin))


def verify_pin(pin: str) -> bool:
    stored = _read_file_hash()
    if not stored:
        return False
    if len(pin) != 6 or not pin.isdigit():
        return False
    return _check_password(pin, stored)


def logs_session_ok(session: dict) -> bool:
    return (not is_pin_configured()) or session.get("pin_verified") is True
