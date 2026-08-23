"""Operator REST endpoints ported from legacy Django (logs, PIN)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .log_buffer import get_log_lines
from .pin_auth import is_pin_configured, verify_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["operator"])

_ROVER_LOG_DIR = Path(
    os.environ.get(
        "BASESTATION_ROVER_LOG_DIR",
        "/workspace/robot_controller/log/logs",
    )
)


class PinVerifyBody(BaseModel):
    pin: str = Field(default="")


@router.get("/status/")
def status_view() -> dict:
    return {"status": "ok", "connected": True}


@router.get("/auth-status/")
def auth_status(request: Request) -> dict:
    return {
        "authenticated": request.session.get("pin_verified") is True,
        "pin_configured": is_pin_configured(),
    }


@router.post("/pin-verify/")
def pin_verify(request: Request, body: PinVerifyBody):
    pin = body.pin.strip()
    if not is_pin_configured():
        return JSONResponse(
            {
                "ok": False,
                "error": "PIN not configured. Run: python3 scripts/set_pin.py 123456",
            },
            status_code=503,
        )
    if not verify_pin(pin):
        return JSONResponse({"ok": False, "error": "Invalid PIN"}, status_code=401)
    request.session["pin_verified"] = True
    return {"ok": True}


@router.get("/django-logs/")
def django_logs() -> dict:
    return {"lines": get_log_lines()}


@router.get("/list-logs/")
def list_logs() -> dict:
    try:
        if not _ROVER_LOG_DIR.is_dir():
            return {"files": []}
        files = sorted(f.name for f in _ROVER_LOG_DIR.glob("*.csv"))
        return {"files": files}
    except OSError as exc:
        logger.error("Error listing rover logs in %s: %s", _ROVER_LOG_DIR, exc)
        raise HTTPException(status_code=500, detail="Failed to list log files") from exc


@router.get("/get-log/{filename}/")
def get_log_file(filename: str) -> dict:
    safe_name = Path(filename).name
    full_path = _ROVER_LOG_DIR / safe_name
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        return {"content": full_path.read_text(encoding="utf-8", errors="replace")}
    except OSError as exc:
        logger.error("Error reading rover log %s: %s", full_path, exc)
        raise HTTPException(status_code=500, detail="Failed to read file") from exc
