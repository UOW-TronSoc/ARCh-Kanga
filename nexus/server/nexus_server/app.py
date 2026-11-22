"""FastAPI entrypoint for the NEXUS container."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from nexus_server.drivestop import DrivestopStore
from nexus_server.drivestop_ros import configure_drivestop
from nexus_server.health import build_health
from nexus_server.ros_runtime import RosRuntime
from nexus_server.spa import mount_spa
from nexus_server.telemetry import TelemetryHub


def create_app(
    *,
    runtime: Optional[object] = None,
    static_dir: Optional[Path] = None,
    drivestop: Optional[DrivestopStore] = None,
    telemetry_hz: Optional[float] = None,
) -> FastAPI:
    selected = runtime if runtime is not None else RosRuntime()
    store = drivestop if drivestop is not None else DrivestopStore()
    rate = telemetry_hz if telemetry_hz is not None else float(os.environ.get("NEXUS_TELEMETRY_HZ", "5"))
    hub = TelemetryHub(store, hz=rate)
    selected.add_configurator(lambda node: configure_drivestop(node, store))
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

    @app.get("/health")
    def health():
        return build_health(selected.status())

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
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

    @app.websocket("/ws/{path:path}")
    async def unknown_ws(websocket: WebSocket, path: str) -> None:
        del path
        await websocket.accept()
        await websocket.close(code=1008)

    mount_spa(app, static_dir)
    return app


app = create_app()
