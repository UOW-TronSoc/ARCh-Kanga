"""
Basestation server entry point.

Phase 1 scaffold (see ../REDESIGN_PLAN.md, task 1): one FastAPI app, one
rclpy node on a background executor thread, static file serving, and a
health endpoint. Control and telemetry WebSockets arrive in later slices.

Run (inside the basestation container, workdir /workspace/basestation):
    python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .commissioning_api import (
    create_commissioning_router,
    create_legacy_commissioning_router,
)
from .commissioning_catalog import build_commissioning_catalog
from .commissioning_config import CommissioningConfigStore
from .commissioning_jobs import CommissioningManager
from .log_buffer import attach_log_buffer
from .launch_api import create_launch_router
from .operator import router as operator_router
from .ros import MAX_LINEAR_MPS, MAX_YAW_RAD_S, TELEMETRY_HZ, RosRuntime
from .spa_static import SPAStaticFiles

runtime = RosRuntime()
commissioning_catalog = build_commissioning_catalog()
commissioning_store = CommissioningConfigStore(commissioning_catalog)
commissioning_manager = CommissioningManager(
    commissioning_catalog,
    commissioning_store,
    runtime,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    attach_log_buffer()
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(title="basestation-server", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("BASESTATION_SECRET_KEY", "dev-change-me-in-production"),
    session_cookie="session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=False,
)
app.include_router(operator_router)
app.include_router(create_launch_router(runtime))
app.include_router(create_commissioning_router(commissioning_manager))
app.include_router(create_legacy_commissioning_router(commissioning_manager))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if runtime.error is None else "degraded",
        "service": "basestation-server",
        "ros_node": runtime.ready,
        "error": runtime.error,
        "core": {**runtime.state.snapshot(), "whs_online": runtime.whs_online()},
        "control": {
            "connected": runtime.control_held(),
            "max_linear_mps": MAX_LINEAR_MPS,
            "max_yaw_rad_s": MAX_YAW_RAD_S,
        },
        "workspace_sourced": os.path.isdir("/workspace/install"),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
    }


class StopRequest(BaseModel):
    stop: bool = Field(description="true = assert drivestop, false = release")


class EnableRequest(BaseModel):
    enable: bool = Field(description="true = closed loop, false = idle")


@app.post("/api/drive/drivestop")
async def api_drivestop(body: StopRequest) -> dict:
    if commissioning_manager.job_active() and not body.stop:
        raise HTTPException(
            status_code=409,
            detail="cannot release drivestop during commissioning",
        )
    return await asyncio.to_thread(runtime.set_drivestop, body.stop)


@app.post("/api/drive/closed-loop")
async def api_closed_loop(body: EnableRequest) -> dict:
    if commissioning_manager.job_active() and body.enable:
        raise HTTPException(
            status_code=409,
            detail="cannot enable closed loop during commissioning",
        )
    return await asyncio.to_thread(runtime.set_closed_loop, body.enable)


@app.post("/api/drive/clear-errors")
async def api_clear_errors() -> dict:
    if commissioning_manager.job_active():
        raise HTTPException(
            status_code=409,
            detail="cannot clear drive errors during commissioning",
        )
    return await asyncio.to_thread(runtime.clear_drive_errors)


# Close code sent to a tab that lost control to a newer one. The page must
# not auto-reconnect on this code, or two tabs would steal control from each
# other once a second forever.
CONTROL_TAKEN = 4000

_holder: Optional[WebSocket] = None


@app.websocket("/ws/control")
async def ws_control(ws: WebSocket) -> None:
    """
    Drive commands from the operator's browser.

    The browser sends small JSON frames at ~20 Hz while driving:
        {"t": "drive", "x": -1..1, "yaw": -1..1, "scale": 0..100}
    The ROS side turns them into /cmd_vel and stops the rover if they stop
    arriving (dead-man).

    Newest tab wins: connecting takes control and the previous holder is
    told it was bumped. A forgotten tab can therefore never lock the
    operator out. This is safe because every reconnect starts with drive
    disabled, so a takeover can only ever stop the rover, not move it.
    """
    global _holder
    await ws.accept()
    old = _holder
    _holder = ws
    if old is not None:
        try:
            await old.close(code=CONTROL_TAKEN, reason="control taken by a newer tab")
        except Exception:  # noqa: BLE001 — old socket may already be dead
            pass
    runtime.on_control_change(connected=True)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("t") == "drive":
                try:
                    runtime.set_drive(
                        float(msg.get("x", 0.0)),
                        float(msg.get("yaw", 0.0)),
                        float(msg.get("scale", 0.0)),
                    )
                except (TypeError, ValueError):
                    pass  # malformed frame: ignore it, dead-man covers us
    except WebSocketDisconnect:
        pass
    finally:
        # Only wind the session down if we are still the holder; if we were
        # bumped, the new tab already owns it.
        if _holder is ws:
            _holder = None
            runtime.on_control_change(connected=False)


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    """
    Push robot state to the operator page at a fixed rate.

    Unlike /ws/control, any number of tabs may listen — this is read-only.
    """
    await ws.accept()
    interval = 1.0 / TELEMETRY_HZ if TELEMETRY_HZ > 0 else 0.2
    try:
        while True:
            await ws.send_json(runtime.telemetry_for_browser())
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — client gone mid-send; normal for tabs
        pass


# Static frontend last so API routes above take precedence.
_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/", SPAStaticFiles(directory=_static_dir, html=True), name="static")
