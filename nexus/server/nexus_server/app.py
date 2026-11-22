"""FastAPI entrypoint for the NEXUS container."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from nexus_server.control import ControlHub
from nexus_server.drive_motion import MotionPublisher
from nexus_server.drivestop import DrivestopStore
from nexus_server.drivestop_ros import configure_drivestop
from nexus_server.health import build_health
from nexus_server.pin import verify_configured_pin
from nexus_server.ros_runtime import RosRuntime
from nexus_server.session import COOKIE_NAME, scope_has_session, session_cookie_ok, sign_session
from nexus_server.spa import mount_spa
from nexus_server.telemetry import TelemetryHub
from nexus_server.whs import RosWhs


class PinBody(BaseModel):
    pin: str


def create_app(
    *,
    runtime: Optional[object] = None,
    static_dir: Optional[Path] = None,
    drivestop: Optional[DrivestopStore] = None,
    telemetry_hz: Optional[float] = None,
    require_pin: Optional[bool] = None,
    session_secret: Optional[str] = None,
    pin_verifier=None,
    whs: Optional[object] = None,
) -> FastAPI:
    selected = runtime if runtime is not None else RosRuntime()
    store = drivestop if drivestop is not None else DrivestopStore()
    rate = telemetry_hz if telemetry_hz is not None else float(os.environ.get("NEXUS_TELEMETRY_HZ", "5"))
    hub = TelemetryHub(store, hz=rate)
    selected.add_configurator(lambda node: configure_drivestop(node, store))
    pin_required = (
        require_pin
        if require_pin is not None
        else os.environ.get("NEXUS_REQUIRE_PIN", "0") == "1"
    )
    secret = session_secret or os.environ.get("NEXUS_SESSION_SECRET") or "nexus-dev-session"
    verifier = pin_verifier or verify_configured_pin
    stop_client = whs if whs is not None else RosWhs(selected)
    motion = MotionPublisher()
    if whs is None:
        selected.add_configurator(stop_client.attach)
        selected.add_configurator(motion.attach)
    control = ControlHub(store, stop_client, motion=motion)
    if static_dir is None and os.environ.get("NEXUS_STATIC_DIR"):
        static_dir = Path(os.environ["NEXUS_STATIC_DIR"])

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        selected.start()
        store.set_ros_available(selected.status().initialized)
        cadence = asyncio.create_task(hub.run())
        try:
            yield
        finally:
            cadence.cancel()
            try:
                await cadence
            except asyncio.CancelledError:
                pass
            selected.stop()

    app = FastAPI(title="NEXUS", lifespan=lifespan)
    app.state.runtime = selected
    app.state.drivestop = store
    app.state.telemetry = hub
    app.state.control = control

    def _authed(scope: dict) -> bool:
        return (not pin_required) or scope_has_session(scope, secret)

    @app.get("/health")
    def health():
        return build_health(selected.status())

    @app.get("/api/session")
    def read_session(request: Request):
        ok = (not pin_required) or session_cookie_ok(request.cookies.get(COOKIE_NAME), secret)
        return {"authenticated": ok}

    @app.post("/api/session")
    def open_session(body: PinBody, response: Response):
        if pin_required:
            accepted, detail = verifier(body.pin)
            if not accepted:
                raise HTTPException(status_code=401, detail=detail or "Incorrect PIN")
        response.set_cookie(COOKIE_NAME, sign_session(secret), httponly=True, samesite="lax", path="/")
        return {"ok": True}

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        if not _authed(websocket.scope):
            await websocket.accept()
            await websocket.close(code=1008)
            return
        await hub.connect(websocket)
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(websocket)

    @app.websocket("/ws/control")
    async def control_socket(websocket: WebSocket) -> None:
        if not _authed(websocket.scope):
            await websocket.accept()
            await websocket.close(code=1008)
            return
        await control.connect(websocket)
        try:
            while True:
                incoming = await websocket.receive()
                if incoming["type"] == "websocket.disconnect":
                    break
                if incoming["type"] != "websocket.receive":
                    continue
                raw = incoming.get("text")
                if not raw:
                    continue
                try:
                    import json

                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    await control.handle(websocket, payload)
        except WebSocketDisconnect:
            pass
        finally:
            control.disconnect(websocket)

    @app.websocket("/ws/{path:path}")
    async def unknown_ws(websocket: WebSocket, path: str) -> None:
        del path
        await websocket.accept()
        await websocket.close(code=1008)

    mount_spa(app, static_dir)
    return app


app = create_app()
