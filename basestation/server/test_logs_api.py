"""ASGI tests for the ROS log snapshot route."""

from __future__ import annotations

import asyncio
import json
import logging
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from . import main as main_module
from .log_buffer import LogBufferHandler, get_log_lines
from .operator import django_logs
from .rosout_buffer import ROS_LOG_ERROR


async def asgi_request(app, method: str, path: str, cookie: str | None = None):
    headers = [(b"host", b"testserver"), (b"accept", b"application/json")]
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    request_sent = False
    messages: list[dict] = []

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(response_body.decode("utf-8"))


class LogsApiTests(unittest.TestCase):
    def test_snapshot_returns_serialized_ring_records(self) -> None:
        main_module.runtime.rosout.append_fields(
            stamp_sec=1_700_000_000,
            level=ROS_LOG_ERROR,
            name="/drive_manager",
            msg="fault",
        )
        app = FastAPI()
        app.add_api_route("/api/logs", main_module.api_ros_logs)
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        with patch.object(main_module, "is_pin_configured", return_value=False):
            status_code, body = asyncio.run(asgi_request(app, "GET", "/api/logs"))
        self.assertEqual(status_code, 200)
        self.assertGreaterEqual(len(body["records"]), 1)
        last = body["records"][-1]
        self.assertEqual(last["level_name"], "ERROR")
        self.assertEqual(last["name"], "/drive_manager")
        self.assertEqual(last["msg"], "fault")

    def test_configured_pin_protects_snapshot(self) -> None:
        app = FastAPI()
        app.add_api_route("/api/logs", main_module.api_ros_logs)

        @app.post("/test-login")
        def test_login(request: Request) -> dict:
            request.session["pin_verified"] = True
            return {"ok": True}

        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        with patch.object(main_module, "is_pin_configured", return_value=True):
            status_code, body = asyncio.run(asgi_request(app, "GET", "/api/logs"))
            self.assertEqual(status_code, 401)
            self.assertIn("PIN", body["detail"])

    def test_http_leaf_reads_uvicorn_buffer_lines(self) -> None:
        handler = LogBufferHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(asctime)s %(name)s: %(message)s")
        )
        record = logging.LogRecord(
            "uvicorn.error",
            logging.ERROR,
            pathname="",
            lineno=0,
            msg="startup complete",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        lines = get_log_lines()
        self.assertTrue(any("startup complete" in line for line in lines))
        self.assertTrue(any("ERROR" in line for line in lines))
        body = django_logs()
        self.assertIn("startup complete", "\n".join(body["lines"]))


if __name__ == "__main__":
    unittest.main()
