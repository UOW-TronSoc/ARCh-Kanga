"""Tests for production React Router refresh handling."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from starlette.exceptions import HTTPException

from .spa_static import SPAStaticFiles


def _scope(path: str, accept: str = "text/html", method: str = "GET") -> dict:
    return {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"accept", accept.encode())],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }


class SPAStaticFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        static_directory = Path(self.temp_directory.name)
        (static_directory / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
        self.static = SPAStaticFiles(directory=static_directory, html=True)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def get_response(self, path: str, accept: str = "text/html"):
        return asyncio.run(self.static.get_response(path.lstrip("/"), _scope(path, accept)))

    def test_client_routes_return_the_react_entrypoint(self) -> None:
        for path in ("/commissioning", "/logs", "/dashboard"):
            with self.subTest(path=path):
                response = self.get_response(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Path(response.path).name, "index.html")

    def test_api_json_and_asset_misses_remain_not_found(self) -> None:
        requests = (
            ("/api", "text/html"),
            ("/api/missing", "text/html"),
            ("/health/missing", "text/html"),
            ("/missing", "application/json"),
            ("/assets/missing.js", "text/html"),
        )
        for path, accept in requests:
            with self.subTest(path=path):
                with self.assertRaises(HTTPException) as context:
                    self.get_response(path, accept)
                self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
