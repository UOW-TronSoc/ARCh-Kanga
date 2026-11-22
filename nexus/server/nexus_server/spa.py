"""Serve the built NEXUS frontend without hiding /health or /ws."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_spa(app: FastAPI, static_dir: Path | None) -> None:
    if static_dir is None or not static_dir.is_dir():
        return
    root = static_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "health" or full_path == "ws" or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (root / full_path).resolve() if full_path else root
        if (root == candidate or root in candidate.parents) and candidate.is_file():
            return FileResponse(candidate)
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not found")
