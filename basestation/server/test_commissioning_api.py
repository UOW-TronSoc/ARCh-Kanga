"""ASGI-level tests for authenticated commissioning HTTP endpoints."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from . import commissioning_api as commissioning_api_module
from .commissioning_api import (
    create_commissioning_router,
    create_legacy_commissioning_router,
)
from .commissioning_catalog import build_commissioning_catalog
from .commissioning_config import CommissioningConfigStore
from .commissioning_jobs import CommissioningManager
from .test_commissioning_config import copy_config_workspace


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.commissioning_active = False

    def set_commissioning_active(self, active: bool) -> None:
        self.commissioning_active = active

    def save_wheel(self, motor_id: str) -> dict:
        self.calls.append(("save", motor_id))
        return {"ok": True, "message": f"saved {motor_id}"}

    def calibrate_wheel(self, motor_id: str) -> dict:
        self.calls.append(("calibrate", motor_id))
        return {"ok": True, "message": f"calibrated {motor_id}"}


async def asgi_request(
    app,
    method: str,
    path: str,
    body: dict | None = None,
    cookie: str | None = None,
) -> tuple[int, dict, dict[str, str]]:
    """Send one request directly to an ASGI app without an HTTP client dependency."""
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = [(b"host", b"testserver"), (b"accept", b"application/json")]
    if body is not None:
        headers.append((b"content-type", b"application/json"))
        headers.append((b"content-length", str(len(payload)).encode("ascii")))
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
            return {"type": "http.request", "body": payload, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    response_headers = {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in start["headers"]
    }
    decoded_body = json.loads(response_body.decode("utf-8"))
    return start["status"], decoded_body, response_headers


class CommissioningApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        workspace = Path(self.temporary_directory.name)
        copy_config_workspace(workspace)
        catalog = build_commissioning_catalog(workspace)
        self.runtime = FakeRuntime()
        self.manager = CommissioningManager(
            catalog,
            CommissioningConfigStore(catalog),
            self.runtime,
        )

        self.app = FastAPI()
        self.app.include_router(create_commissioning_router(self.manager))
        self.app.include_router(create_legacy_commissioning_router(self.manager))

        @self.app.post("/test-login")
        def test_login(request: Request) -> dict:
            request.session["pin_verified"] = True
            return {"ok": True}

        self.app.add_middleware(SessionMiddleware, secret_key="test-secret")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        cookie: str | None = None,
        pin_configured: bool = False,
    ) -> tuple[int, dict, dict[str, str]]:
        with patch.object(
            commissioning_api_module,
            "is_pin_configured",
            return_value=pin_configured,
        ):
            return asyncio.run(
                asgi_request(self.app, method, path, body=body, cookie=cookie)
            )

    def authenticated_cookie(self) -> str:
        status_code, _, headers = self.request(
            "POST",
            "/test-login",
            pin_configured=True,
        )
        self.assertEqual(status_code, 200)
        return headers["set-cookie"].split(";", 1)[0]

    def test_pin_session_protects_catalog_and_config_reads(self) -> None:
        status_code, body, _ = self.request(
            "GET",
            "/api/commissioning/catalog",
            pin_configured=True,
        )
        self.assertEqual(status_code, 401)
        self.assertIn("PIN authentication", body["detail"])

        cookie = self.authenticated_cookie()
        status_code, catalog, _ = self.request(
            "GET",
            "/api/commissioning/catalog",
            cookie=cookie,
            pin_configured=True,
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(catalog["subsystems"][0]["id"], "core")

        status_code, shared, _ = self.request(
            "GET",
            "/api/commissioning/configs/core/shared",
            cookie=cookie,
            pin_configured=True,
        )
        self.assertEqual(status_code, 200)
        self.assertIn("spinout_mechanical_power_threshold", shared["content"])

    def test_no_pin_configuration_keeps_development_access_open(self) -> None:
        status_code, body, _ = self.request(
            "GET",
            "/api/commissioning/catalog",
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(body["subsystems"]), 3)

    def test_config_put_uses_revision_and_validation(self) -> None:
        _, shared, _ = self.request(
            "GET",
            "/api/commissioning/configs/core/shared",
        )
        changed = shared["content"] + "\nodrv.config.enable_uart_b = False\n"
        status_code, saved, _ = self.request(
            "PUT",
            "/api/commissioning/configs/core/shared",
            {"content": changed, "revision": shared["revision"]},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(saved["content"], changed)

        status_code, stale, _ = self.request(
            "PUT",
            "/api/commissioning/configs/core/shared",
            {"content": shared["content"], "revision": shared["revision"]},
        )
        self.assertEqual(status_code, 409)
        self.assertIn("reload", stale["detail"])

        status_code, invalid, _ = self.request(
            "PUT",
            "/api/commissioning/configs/core/shared",
            {"content": "import os\n", "revision": saved["revision"]},
        )
        self.assertEqual(status_code, 422)
        self.assertIn("only declarative assignments", invalid["detail"])

    def test_calibration_job_waits_for_each_confirm_endpoint(self) -> None:
        status_code, created, _ = self.request(
            "POST",
            "/api/commissioning/jobs",
            {
                "subsystem": "core",
                "operation": "calibrate",
                "motor_ids": ["bl", "fl"],
            },
        )
        self.assertEqual(status_code, 201)
        self.assertEqual(created["state"], "awaiting_confirmation")
        self.assertEqual(created["items"][0]["motor_id"], "fl")
        self.assertEqual(self.runtime.calls, [])

        status_code, _, _ = self.request(
            "POST",
            f"/api/commissioning/jobs/{created['id']}/confirm",
        )
        self.assertEqual(status_code, 200)
        waiting = self.wait_for_job_state(created["id"], "awaiting_confirmation")
        self.assertEqual(waiting["items"][1]["motor_id"], "bl")
        self.assertEqual(self.runtime.calls, [("calibrate", "fl")])

        self.request(
            "POST",
            f"/api/commissioning/jobs/{created['id']}/confirm",
        )
        terminal = self.wait_for_job_state(created["id"], "succeeded")
        self.assertEqual(terminal["state"], "succeeded")
        self.assertEqual(
            self.runtime.calls,
            [("calibrate", "fl"), ("calibrate", "bl")],
        )

    def test_failed_save_can_be_retried_through_api(self) -> None:
        attempts = 0

        def fail_once(motor_id: str) -> dict:
            nonlocal attempts
            self.runtime.calls.append(("save", motor_id))
            attempts += 1
            if attempts == 1:
                return {"ok": False, "message": "temporary CAN error"}
            return {"ok": True, "message": f"saved {motor_id}"}

        self.runtime.save_wheel = fail_once
        status_code, created, _ = self.request(
            "POST",
            "/api/commissioning/jobs",
            {"subsystem": "core", "operation": "save", "motor_ids": ["fl"]},
        )
        self.assertEqual(status_code, 201)
        self.wait_for_job_state(created["id"], "failed")

        status_code, retrying, _ = self.request(
            "POST",
            f"/api/commissioning/jobs/{created['id']}/retry",
        )
        self.assertEqual(status_code, 200)
        self.assertIn(retrying["state"], {"pending", "running", "succeeded"})
        terminal = self.wait_for_job_state(created["id"], "succeeded")
        self.assertEqual(terminal["items"][0]["state"], "succeeded")

    def test_failed_multi_motor_job_can_be_skipped_through_api(self) -> None:
        def fail_front_left(motor_id: str) -> dict:
            self.runtime.calls.append(("save", motor_id))
            if motor_id == "fl":
                return {"ok": False, "message": "front left unavailable"}
            return {"ok": True, "message": f"saved {motor_id}"}

        self.runtime.save_wheel = fail_front_left
        _, created, _ = self.request(
            "POST",
            "/api/commissioning/jobs",
            {
                "subsystem": "core",
                "operation": "save",
                "motor_ids": ["fl", "bl"],
            },
        )
        self.wait_for_job_state(created["id"], "failed")

        status_code, _, _ = self.request(
            "POST",
            f"/api/commissioning/jobs/{created['id']}/skip",
        )
        self.assertEqual(status_code, 200)
        terminal = self.wait_for_job_state(created["id"], "completed_with_skips")
        self.assertEqual(
            [item["state"] for item in terminal["items"]],
            ["skipped", "succeeded"],
        )

    def test_legacy_calibration_route_uses_a_confirmed_one_motor_job(self) -> None:
        status_code, rejected, _ = self.request(
            "POST",
            "/api/drive/calibrate/br",
            {"off_ground_confirmed": False},
        )
        self.assertEqual(status_code, 400)
        self.assertIn("off-ground confirmation", rejected["detail"])

        status_code, result, _ = self.request(
            "POST",
            "/api/drive/calibrate/br",
            {"off_ground_confirmed": True},
        )
        self.assertEqual(status_code, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "calibrated br")
        self.assertTrue(result["job_id"])

    def test_legacy_calibration_failure_releases_job_interlock(self) -> None:
        def fail_calibration(motor_id: str) -> dict:
            self.runtime.calls.append(("calibrate", motor_id))
            return {"ok": False, "message": "calibration failed"}

        self.runtime.calibrate_wheel = fail_calibration
        status_code, result, _ = self.request(
            "POST",
            "/api/drive/calibrate/fl",
            {"off_ground_confirmed": True},
        )

        self.assertEqual(status_code, 200)
        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "calibration failed")
        self.assertFalse(self.manager.job_active())

    def wait_for_job_state(self, job_id: str, expected_state: str) -> dict:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            status_code, job, _ = self.request(
                "GET",
                f"/api/commissioning/jobs/{job_id}",
            )
            self.assertEqual(status_code, 200)
            if job["state"] == expected_state:
                return job
            time.sleep(0.005)
        self.fail(f"job did not reach {expected_state}")


if __name__ == "__main__":
    unittest.main()
