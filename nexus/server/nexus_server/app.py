"""FastAPI entrypoint for the NEXUS container."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket

from nexus_server.health import build_health
from nexus_server.ros_runtime import RosRuntime
from nexus_server.spa import mount_spa


def create_app(
    *,
    runtime: Optional[object] = None,
    static_dir: Optional[Path] = None,
) -> FastAPI:
    selected = runtime if runtime is not None else RosRuntime()
    if static_dir is None and os.environ.get("NEXUS_STATIC_DIR"):
        static_dir = Path(os.environ["NEXUS_STATIC_DIR"])

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        selected.start()
        yield
        selected.stop()

    app = FastAPI(title="NEXUS", lifespan=lifespan)
    app.state.runtime = selected

    @app.get("/health")
    def health():
        return build_health(selected.status())

    @app.websocket("/ws/{path:path}")
    async def unknown_ws(websocket: WebSocket, path: str) -> None:
        del path
        await websocket.accept()
        await websocket.close(code=1008)

    mount_spa(app, static_dir)
    return app


app = create_app()
