"""Host-shell PTY for the operator Terminal page.

On native Linux (pid:host + privileged basestation compose overlay) the shell
is started via nsenter into host PID 1 so it matches an SSH login. Elsewhere
the WebSocket reports that the host terminal is unavailable.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pwd
import pty
import shutil
import signal
import struct
import subprocess
import termios
from pathlib import Path
from typing import Callable, Optional, Sequence

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .pin_auth import logs_session_ok

MAX_SESSIONS = 4
DEFAULT_COLS = 80
DEFAULT_ROWS = 24
READ_CHUNK = 4096

_DEFAULT_WORKSPACE = Path("/workspace")

_active_sessions = 0
_sessions_lock = asyncio.Lock()


def host_workspace() -> Path:
    raw = os.environ.get("KANGA_HOST_WORKSPACE", "").strip()
    if raw:
        return Path(raw)
    # Bind mount: /workspace is the repo root inside the container.
    if _DEFAULT_WORKSPACE.is_dir():
        return _DEFAULT_WORKSPACE
    return Path.cwd().resolve().parent


def host_uid_gid() -> tuple[int, int]:
    workspace = host_workspace()
    try:
        uid = int(os.environ.get("KANGA_UID", "") or workspace.stat().st_uid)
    except (TypeError, ValueError, OSError):
        uid = os.getuid()
    try:
        gid = int(os.environ.get("KANGA_GID", "") or workspace.stat().st_gid)
    except (TypeError, ValueError, OSError):
        gid = os.getgid()
    return uid, gid


def host_user_home(uid: Optional[int] = None) -> Path:
    """Return the host user's home directory for bash profile/aliases.

    The container passwd database may not match the host uid, so prefer
    KANGA_USER_HOME set by basestation_up.bash on the host.
    """
    raw = os.environ.get("KANGA_USER_HOME", "").strip()
    if raw:
        return Path(raw)
    if uid is None:
        uid, _ = host_uid_gid()
    try:
        return Path(pwd.getpwuid(uid).pw_dir)
    except (KeyError, OSError):
        return host_workspace()


def same_pid_namespace_as_init() -> bool:
    """True when this process shares PID 1's namespace (pid: host)."""
    try:
        return os.path.samefile("/proc/self/ns/pid", "/proc/1/ns/pid")
    except OSError:
        return False


def host_terminal_available() -> tuple[bool, str]:
    if shutil.which("nsenter") is None:
        return False, "nsenter is not installed in the basestation image"
    if shutil.which("setpriv") is None:
        return False, "setpriv is not installed in the basestation image"
    if not same_pid_namespace_as_init():
        return (
            False,
            "Host terminal requires native Linux with pid:host "
            "(compose.basestation.host.yaml). Unavailable on Docker Desktop / WSL2.",
        )
    # KANGA_HOST_WORKSPACE is a host path; it may not exist in the container
    # mount namespace before nsenter. Require the env (or /workspace bind).
    raw = os.environ.get("KANGA_HOST_WORKSPACE", "").strip()
    if not raw and not _DEFAULT_WORKSPACE.is_dir():
        return False, "KANGA_HOST_WORKSPACE is unset and /workspace is missing"
    return True, ""


def build_host_shell_argv(
    workspace: Optional[Path] = None,
    uid: Optional[int] = None,
    gid: Optional[int] = None,
) -> list[str]:
    """Build nsenter + setpriv + bash argv for a host interactive shell.

    Popen cwd must stay a path that exists in the container (/). After nsenter
    switches to the host mount namespace, bash cds into KANGA_HOST_WORKSPACE.
    HOME stays the user's real home so ~/.bashrc aliases and colors load.
    """
    ws = workspace or host_workspace()
    if uid is None or gid is None:
        resolved_uid, resolved_gid = host_uid_gid()
        uid = resolved_uid if uid is None else uid
        gid = resolved_gid if gid is None else gid
    home = host_user_home(uid)
    # HISTFILE lives on the bind-mounted workspace so it persists on the host.
    hist = Path(ws) / "basestation" / "data" / ".web_terminal_history"
    # Already share the host PID namespace (compose pid: host). Do not pass
    # --pid to nsenter: re-entering the PID namespace breaks PTY job control.
    return [
        "nsenter",
        "--target",
        "1",
        "--mount",
        "--uts",
        "--ipc",
        "--net",
        "--",
        "setpriv",
        f"--reuid={uid}",
        f"--regid={gid}",
        "--init-groups",
        "--",
        "env",
        f"HOME={home}",
        f"KANGA_HOST_WORKSPACE={ws}",
        f"HISTFILE={hist}",
        "TERM=xterm-256color",
        "COLORTERM=truecolor",
        f"PWD={ws}",
        "/bin/bash",
        "-c",
        'cd "${KANGA_HOST_WORKSPACE:-$HOME}" && exec /bin/bash -i',
    ]


def _set_winsize(fd: int, cols: int, rows: int) -> None:
    cols = max(1, min(int(cols), 512))
    rows = max(1, min(int(rows), 512))
    packed = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


class TerminalSession:
    """One interactive PTY bound to a WebSocket."""

    def __init__(
        self,
        argv: Sequence[str],
        cwd: Path,
        cols: int = DEFAULT_COLS,
        rows: int = DEFAULT_ROWS,
        env: Optional[dict[str, str]] = None,
    ) -> None:
        self.argv = list(argv)
        self.cwd = Path(cwd)
        self.env = env
        self.master_fd: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self._closed = False
        self._spawn(cols, rows)

    def _spawn(self, cols: int, rows: int) -> None:
        master_fd, slave_fd = pty.openpty()
        _set_winsize(master_fd, cols, rows)

        def _child_setup() -> None:
            # New session + claim the PTY as controlling tty so bash gets
            # job control (Ctrl-C, fg/bg) like an SSH login.
            os.setsid()
            try:
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            except OSError:
                pass

        try:
            self.proc = subprocess.Popen(
                self.argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(self.cwd),
                env=self.env,
                preexec_fn=_child_setup,
                close_fds=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)
        # Non-blocking reads from the master.
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.master_fd = master_fd

    def resize(self, cols: int, rows: int) -> None:
        if self.master_fd is not None:
            _set_winsize(self.master_fd, cols, rows)

    def write(self, data: bytes) -> None:
        if self.master_fd is None or not data:
            return
        view = memoryview(data)
        while view:
            try:
                n = os.write(self.master_fd, view)
            except BlockingIOError:
                break
            except OSError:
                break
            view = view[n:]

    def read(self) -> bytes:
        if self.master_fd is None:
            return b""
        chunks: list[bytes] = []
        while True:
            try:
                chunk = os.read(self.master_fd, READ_CHUNK)
            except BlockingIOError:
                break
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.proc is not None and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            except PermissionError:
                pass
            try:
                self.proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    pass
                try:
                    self.proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None


SpawnFactory = Callable[..., TerminalSession]


def default_spawn(
    cols: int = DEFAULT_COLS,
    rows: int = DEFAULT_ROWS,
) -> TerminalSession:
    ok, message = host_terminal_available()
    if not ok:
        raise RuntimeError(message)
    workspace = host_workspace()
    # Start in / (exists pre-nsenter); bash cds to HOME after entering host ns.
    return TerminalSession(
        argv=build_host_shell_argv(workspace),
        cwd=Path("/"),
        cols=cols,
        rows=rows,
    )


async def run_terminal_websocket(
    ws: WebSocket,
    *,
    spawn: SpawnFactory = default_spawn,
    session_ok: Callable[[dict], bool] = logs_session_ok,
) -> None:
    """Accept, authenticate, spawn a PTY, and bridge bytes until disconnect."""
    global _active_sessions
    await ws.accept()
    session = ws.scope.get("session") or {}
    if not session_ok(session):
        await ws.send_text(
            json.dumps(
                {
                    "t": "error",
                    "message": "PIN authentication is required for the terminal",
                }
            )
        )
        await ws.close(code=4401)
        return

    async with _sessions_lock:
        if _active_sessions >= MAX_SESSIONS:
            await ws.send_text(
                json.dumps(
                    {
                        "t": "error",
                        "message": f"Too many terminal sessions (max {MAX_SESSIONS})",
                    }
                )
            )
            await ws.close(code=4403)
            return
        _active_sessions += 1

    term: Optional[TerminalSession] = None
    try:
        try:
            term = spawn(cols=DEFAULT_COLS, rows=DEFAULT_ROWS)
        except Exception as exc:  # noqa: BLE001 — surface spawn failures to UI
            await ws.send_text(
                json.dumps({"t": "error", "message": str(exc) or "failed to start shell"})
            )
            await ws.close(code=4400)
            return

        await ws.send_text(json.dumps({"t": "ready", "cwd": str(host_workspace())}))

        async def pump_output() -> None:
            assert term is not None
            while term.alive() and ws.client_state == WebSocketState.CONNECTED:
                data = await asyncio.to_thread(term.read)
                if data:
                    await ws.send_bytes(data)
                else:
                    await asyncio.sleep(0.02)
            # Drain any final output after the process exits.
            data = await asyncio.to_thread(term.read)
            if data and ws.client_state == WebSocketState.CONNECTED:
                await ws.send_bytes(data)
            if ws.client_state == WebSocketState.CONNECTED:
                code = term.proc.returncode if term.proc is not None else None
                await ws.send_text(json.dumps({"t": "exit", "code": code}))

        out_task = asyncio.create_task(pump_output())
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    term.write(message["bytes"])
                    continue
                text = message.get("text")
                if text is None:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    # Treat bare text as stdin (some clients send UTF-8 text).
                    term.write(text.encode("utf-8", errors="replace"))
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("t") == "resize":
                    try:
                        term.resize(
                            int(payload.get("cols", DEFAULT_COLS)),
                            int(payload.get("rows", DEFAULT_ROWS)),
                        )
                    except (TypeError, ValueError):
                        pass
        except WebSocketDisconnect:
            pass
        finally:
            out_task.cancel()
            try:
                await out_task
            except asyncio.CancelledError:
                pass
    finally:
        if term is not None:
            await asyncio.to_thread(term.close)
        async with _sessions_lock:
            _active_sessions = max(0, _active_sessions - 1)


def reset_session_counter_for_tests() -> None:
    global _active_sessions
    _active_sessions = 0
