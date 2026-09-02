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
from .log_buffer import LogBufferHandler, clear_log_lines, get_log_lines
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
        with patch("server.pin_auth.is_pin_configured", return_value=False):
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
        with patch("server.pin_auth.is_pin_configured", return_value=True):
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

    def test_clear_http_logs_only_clears_uvicorn_buffer(self) -> None:
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
        self.assertTrue(get_log_lines())
        clear_log_lines()
        self.assertEqual(get_log_lines(), [])

    def test_clear_ros_logs_respects_selection_leaf(self) -> None:
        main_module.runtime.rosout.clear()
        main_module.runtime.rosout.append_fields(
            level=ROS_LOG_ERROR,
            name="wheel_bl.can_node",
            msg="left",
        )
        main_module.runtime.rosout.append_fields(
            level=ROS_LOG_ERROR,
            name="wheel_fr.can_node",
            msg="right",
        )
        app = FastAPI()
        app.add_api_route("/api/logs/clear", main_module.api_ros_logs_clear, methods=["POST"])
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        with patch("server.pin_auth.is_pin_configured", return_value=False):
            status_code, body = asyncio.run(
                asgi_post(
                    app,
                    "/api/logs/clear",
                    {"selection_type": "prefix", "path": "wheel_bl"},
                )
            )
        self.assertEqual(status_code, 200)
        self.assertTrue(body["ok"])
        records = main_module.runtime.rosout.snapshot()
        self.assertEqual([item["msg"] for item in records], ["right"])


async def asgi_post(app, path: str, payload: dict, cookie: str | None = None):
    body = json.dumps(payload).encode("utf-8")
    headers = [
        (b"host", b"testserver"),
        (b"accept", b"application/json"),
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
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
            return {"type": "http.request", "body": body, "more_body": False}
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


if __name__ == "__main__":
    unittest.main()
