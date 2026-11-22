"""Load ARCh's PIN helper without starting the legacy basestation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType


def _pin_module() -> ModuleType | None:
    candidates = []
    configured = os.environ.get("NEXUS_PIN_AUTH")
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path("/workspace/basestation/server/pin_auth.py"))
    candidates.append(Path(__file__).resolve().parents[3] / "basestation" / "server" / "pin_auth.py")
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("arch_pin_auth", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def verify_configured_pin(pin: str) -> tuple[bool, str | None]:
    module = _pin_module()
    if module is None or not module.is_pin_configured():
        return False, "PIN is not configured"
    if module.verify_pin(pin):
        return True, None
    return False, "Incorrect PIN"
