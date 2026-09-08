"""Tests for the host Terminal PTY helper and WebSocket bridge."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, WebSocket

from . import terminal_pty as terminal_module
from .terminal_pty import (
    TerminalSession,
    build_host_shell_argv,
    host_terminal_available,
    host_uid_gid,
    host_workspace,
    reset_session_counter_for_tests,
    run_terminal_websocket,
)


def _local_bash_spawn(cols: int = 80, rows: int = 24) -> TerminalSession:
    """Spawn a local interactive bash without nsenter (unit-test path)."""
    return TerminalSession(
        argv=["/bin/bash", "--norc", "--noprofile", "-i"],
        cwd=Path("/"),
        cols=cols,
        rows=rows,
        env={
            "HOME": "/",
            "TERM": "xterm-256color",
            "PS1": "test$ ",
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        },
    )


async def asgi_websocket(
    app,
    path: str,
    *,
    client_messages: list[dict],
    session: dict | None = None,
) -> list[dict]:
    """Drive a WebSocket ASGI endpoint and collect server send messages."""
    headers = [(b"host", b"testserver"), (b"sec-websocket-key", b"dGVzdA==")]
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "subprotocols": [],
        "state": {},
        "session": session or {},
    }
    queue = list(client_messages)
    messages: list[dict] = []

    async def receive() -> dict:
        if queue:
            return queue.pop(0)
        await asyncio.sleep(0.05)
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(message: dict) -> None:
        messages.append(message)

    await app(scope, receive, send)
    return messages


class HostShellArgvTests(unittest.TestCase):
    def test_build_host_shell_argv_uses_nsenter_setpriv_and_workspace(self) -> None:
        argv = build_host_shell_argv(
            workspace=Path("/home/kanga/kanga_wip"),
            uid=1000,
            gid=1000,
        )
        self.assertEqual(argv[0], "nsenter")
        self.assertIn("--target", argv)
        self.assertIn("1", argv)
        self.assertIn("--mount", argv)
        self.assertNotIn("--pid", argv)
        self.assertIn("setpriv", argv)
        self.assertIn("--reuid=1000", argv)
        self.assertIn("--regid=1000", argv)
        self.assertIn("--init-groups", argv)
        self.assertIn("HOME=/home/kanga/kanga_wip", argv)
        self.assertIn(
            "HISTFILE=/home/kanga/kanga_wip/basestation/data/.web_terminal_history",
            argv,
        )
        self.assertIn("/bin/bash", argv)
        self.assertIn('cd "$HOME" && exec /bin/bash -i', argv)

    def test_host_workspace_prefers_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"KANGA_HOST_WORKSPACE": tmp}):
                self.assertEqual(host_workspace(), Path(tmp))

    def test_host_uid_gid_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                os.environ,
                {
                    "KANGA_HOST_WORKSPACE": tmp,
                    "KANGA_UID": "4242",
                    "KANGA_GID": "4243",
                },
            ):
                self.assertEqual(host_uid_gid(), (4242, 4243))

    def test_unavailable_without_shared_pid_namespace(self) -> None:
        with patch.object(terminal_module, "same_pid_namespace_as_init", return_value=False):
            with patch.object(shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
                ok, message = host_terminal_available()
        self.assertFalse(ok)
        self.assertIn("pid:host", message)


@unittest.skipUnless(shutil.which("bash"), "bash required")
class LocalPtySessionTests(unittest.TestCase):
    def test_echo_resize_and_kill(self) -> None:
        session = _local_bash_spawn()
        try:
            deadline = time.time() + 2.0
            while time.time() < deadline:
                session.read()
                time.sleep(0.05)
            session.write(b"printf 'hello-pty\\n'\n")
            got = b""
            deadline = time.time() + 3.0
            while time.time() < deadline and b"hello-pty" not in got:
                got += session.read()
                time.sleep(0.05)
            self.assertIn(b"hello-pty", got)
            session.resize(100, 40)
            self.assertTrue(session.alive())
        finally:
            session.close()
        self.assertFalse(session.alive())


class TerminalWebsocketTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_counter_for_tests()

    def tearDown(self) -> None:
        reset_session_counter_for_tests()

    def _app(self) -> FastAPI:
        app = FastAPI()

        @app.websocket("/ws/terminal")
        async def ws_terminal(ws: WebSocket):
            await run_terminal_websocket(ws, spawn=_local_bash_spawn)

        return app

    def test_pin_rejects_unauthenticated_session(self) -> None:
        app = self._app()
        with patch("server.pin_auth.is_pin_configured", return_value=True):
            messages = asyncio.run(
                asgi_websocket(
                    app,
                    "/ws/terminal",
                    client_messages=[{"type": "websocket.connect"}],
                    session={},
                )
            )
        texts = [
            json.loads(m["text"])
            for m in messages
            if m["type"] == "websocket.send" and "text" in m
        ]
        self.assertTrue(texts)
        self.assertEqual(texts[0]["t"], "error")
        self.assertIn("PIN", texts[0]["message"])
        closes = [m for m in messages if m["type"] == "websocket.close"]
        self.assertTrue(closes)
        self.assertEqual(closes[0].get("code"), 4401)

    def test_local_shell_echo_and_resize_over_websocket(self) -> None:
        app = self._app()

        async def exercise() -> bytes:
            headers = [
                (b"host", b"testserver"),
                (b"sec-websocket-key", b"dGVzdA=="),
            ]
            scope = {
                "type": "websocket",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "scheme": "ws",
                "path": "/ws/terminal",
                "raw_path": b"/ws/terminal",
                "query_string": b"",
                "headers": headers,
                "client": ("127.0.0.1", 1234),
                "server": ("testserver", 80),
                "subprotocols": [],
                "state": {},
                "session": {},
            }
            out_q: asyncio.Queue = asyncio.Queue()
            in_q: asyncio.Queue = asyncio.Queue()
            await in_q.put({"type": "websocket.connect"})

            async def receive() -> dict:
                return await in_q.get()

            async def send(message: dict) -> None:
                await out_q.put(message)

            task = asyncio.create_task(app(scope, receive, send))
            # Wait for accept + ready.
            got = b""
            ready = False
            deadline = time.time() + 4.0
            while time.time() < deadline and not ready:
                try:
                    msg = await asyncio.wait_for(out_q.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if msg["type"] == "websocket.accept":
                    continue
                if msg["type"] == "websocket.send" and "text" in msg:
                    payload = json.loads(msg["text"])
                    if payload.get("t") == "ready":
                        ready = True
                        break
                    if payload.get("t") == "error":
                        task.cancel()
                        raise AssertionError(payload.get("message"))
            self.assertTrue(ready)
            await in_q.put(
                {
                    "type": "websocket.receive",
                    "text": json.dumps({"t": "resize", "cols": 100, "rows": 30}),
                }
            )
            await in_q.put(
                {
                    "type": "websocket.receive",
                    "bytes": b"printf 'ws-pty-ok\\n'\n",
                }
            )
            deadline = time.time() + 4.0
            while time.time() < deadline and b"ws-pty-ok" not in got:
                try:
                    msg = await asyncio.wait_for(out_q.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if msg["type"] == "websocket.send" and "bytes" in msg:
                    got += msg["bytes"]
            await in_q.put({"type": "websocket.disconnect", "code": 1000})
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except asyncio.TimeoutError:
                task.cancel()
            return got

        with patch("server.pin_auth.is_pin_configured", return_value=False):
            got = asyncio.run(exercise())
        self.assertIn(b"ws-pty-ok", got)


class SessionCapTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_counter_for_tests()

    def tearDown(self) -> None:
        reset_session_counter_for_tests()

    def test_session_cap_returns_error(self) -> None:
        app = FastAPI()

        @app.websocket("/ws/terminal")
        async def ws_terminal(ws: WebSocket):
            await run_terminal_websocket(ws, spawn=_local_bash_spawn)

        terminal_module._active_sessions = terminal_module.MAX_SESSIONS
        with patch("server.pin_auth.is_pin_configured", return_value=False):
            messages = asyncio.run(
                asgi_websocket(
                    app,
                    "/ws/terminal",
                    client_messages=[{"type": "websocket.connect"}],
                    session={},
                )
            )
        texts = [
            json.loads(m["text"])
            for m in messages
            if m["type"] == "websocket.send" and "text" in m
        ]
        self.assertTrue(texts)
        self.assertEqual(texts[0]["t"], "error")
        self.assertIn("Too many", texts[0]["message"])


if __name__ == "__main__":
    unittest.main()
