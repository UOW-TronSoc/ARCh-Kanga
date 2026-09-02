"""ASGI-level tests for the system-startup REST boundary."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from . import launch_api as launch_api_module
from .launch_api import create_launch_router


CORE_STATUS = {
    "id": "core",
    "label": "Core Rover",
    "state": "STOPPED",
    "health": "NOT_CHECKED",
    "available": True,
    "owned": False,
    "allowed_actions": ["start"],
    "started_at": None,
    "transitioned_at": "2026-08-30T00:00:00+00:00",
    "exit_code": None,
    "last_error": None,
}


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.list_result = {
            "ok": True,
            "message": "",
            "systems": [dict(CORE_STATUS)],
        }
        self.change_result = {
            "ok": True,
            "message": "",
            "system": {**CORE_STATUS, "state": "STARTING"},
        }

    def list_managed_launches(self) -> dict:
        return self.list_result

    def change_managed_launch(self, system_id: str, action: str) -> dict:
        self.calls.append((system_id, action))
        return self.change_result


async def asgi_request(
    app,
    method: str,
    path: str,
    cookie: str | None = None,
) -> tuple[int, dict, dict[str, str]]:
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
    response_headers = {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in start["headers"]
    }
    return (
        start["status"],
        json.loads(response_body.decode("utf-8")),
        response_headers,
    )


class LaunchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = FakeRuntime()
        self.app = FastAPI()
        self.app.include_router(create_launch_router(self.runtime))

        @self.app.post("/test-login")
        def test_login(request: Request) -> dict:
            request.session["pin_verified"] = True
            return {"ok": True}

        self.app.add_middleware(SessionMiddleware, secret_key="test-secret")

    def request(
        self,
        method: str,
        path: str,
        *,
        cookie: str | None = None,
        pin_configured: bool = False,
    ) -> tuple[int, dict, dict[str, str]]:
        with patch.object(
            launch_api_module,
            "is_pin_configured",
            return_value=pin_configured,
        ):
            return asyncio.run(asgi_request(self.app, method, path, cookie))

    def test_lists_agent_owned_public_status(self) -> None:
        status_code, body, _ = self.request("GET", "/api/systems")

        self.assertEqual(status_code, 200)
        self.assertEqual(body, {"systems": [CORE_STATUS]})

    def test_fixed_routes_map_to_only_three_actions(self) -> None:
        for action in ("start", "stop", "restart"):
            with self.subTest(action=action):
                status_code, body, _ = self.request(
                    "POST", f"/api/systems/core/{action}"
                )
                self.assertEqual(status_code, 200)
                self.assertEqual(body["state"], "STARTING")

        self.assertEqual(
            self.runtime.calls,
            [("core", "start"), ("core", "stop"), ("core", "restart")],
        )
        status_code, _, _ = self.request(
            "POST", "/api/systems/core/run-command"
        )
        self.assertEqual(status_code, 404)

    def test_agent_rejection_is_a_conflict(self) -> None:
        self.runtime.change_result = {
            "ok": False,
            "error": "rejected",
            "message": "cannot start core while it is UNMANAGED",
        }

        status_code, body, _ = self.request(
            "POST", "/api/systems/core/start"
        )

        self.assertEqual(status_code, 409)
        self.assertIn("UNMANAGED", body["detail"])

    def test_unreachable_agent_is_service_unavailable(self) -> None:
        self.runtime.list_result = {
            "ok": False,
            "error": "unavailable",
            "message": "onboard launch agent not available",
            "systems": [],
        }

        status_code, body, _ = self.request("GET", "/api/systems")

        self.assertEqual(status_code, 503)
        self.assertIn("not available", body["detail"])

    def test_configured_pin_protects_status_and_actions(self) -> None:
        status_code, _, _ = self.request(
            "GET", "/api/systems", pin_configured=True
        )
        self.assertEqual(status_code, 401)

        _, _, headers = self.request(
            "POST", "/test-login", pin_configured=True
        )
        cookie = headers["set-cookie"].split(";", 1)[0]
        status_code, _, _ = self.request(
            "POST",
            "/api/systems/core/start",
            cookie=cookie,
            pin_configured=True,
        )
        self.assertEqual(status_code, 200)


if __name__ == "__main__":
    unittest.main()
