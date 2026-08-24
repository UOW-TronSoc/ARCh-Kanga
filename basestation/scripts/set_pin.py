#!/usr/bin/env python3
"""Set the 6-digit basestation PIN (stored as PBKDF2 hash in data/.pin_hash)."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo: python3 basestation/scripts/set_pin.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.pin_auth import is_pin_configured, set_pin_hash  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/set_pin.py 123456", file=sys.stderr)
        return 1
    pin = sys.argv[1].strip()
    if len(pin) != 6 or not pin.isdigit():
        print("PIN must be exactly 6 digits", file=sys.stderr)
        return 1
    if is_pin_configured():
        print("PIN already set. Delete data/.pin_hash first to reset.", file=sys.stderr)
        return 1
    set_pin_hash(pin)
    print("PIN set successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
