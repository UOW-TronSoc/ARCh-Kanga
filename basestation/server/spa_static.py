"""Static-file serving with a constrained React Router fallback."""

from __future__ import annotations

from pathlib import PurePosixPath

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


def _is_spa_navigation(path: str, scope: Scope) -> bool:
    """Return whether a missing static path is a browser page navigation."""
    if scope["method"] not in ("GET", "HEAD"):
        return False

    normalized_path = path.lstrip("/")
    if normalized_path.partition("/")[0] in {"api", "health", "ws"}:
        return False
    if PurePosixPath(normalized_path).suffix:
        return False

    return "text/html" in Headers(scope=scope).get("accept", "").lower()


class SPAStaticFiles(StaticFiles):
    """Serve index.html for missing client routes, while preserving real 404s."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or not _is_spa_navigation(path, scope):
                raise
            return await super().get_response("index.html", scope)
