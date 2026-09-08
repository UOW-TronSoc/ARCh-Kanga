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
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Sequence

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .pin_auth import logs_session_ok

MAX_SESSIONS = 6
DEFAULT_COLS = 80
DEFAULT_ROWS = 24
READ_CHUNK = 4096
MAX_SCROLLBACK_BYTES = 512 * 1024
DETACHED_TTL_SEC = 3600

_DEFAULT_WORKSPACE = Path("/workspace")

_managed_sessions: dict[str, "ManagedTerminalSession"] = {}
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


class ManagedTerminalSession:
    """PTY kept alive across browser disconnects; one WebSocket attaches at a time."""

    def __init__(self, term: TerminalSession, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.term = term
        self.scrollback = bytearray()
        self._ws: Optional[WebSocket] = None
        self._pump_task: Optional[asyncio.Task] = None
        self.detached_at: Optional[float] = None
        self.explicit_close = False

    def alive(self) -> bool:
        return self.term.alive()

    def _append_scrollback(self, data: bytes) -> None:
        if not data:
            return
        self.scrollback.extend(data)
        overflow = len(self.scrollback) - MAX_SCROLLBACK_BYTES
        if overflow > 0:
            del self.scrollback[:overflow]

    async def start_pump(self) -> None:
        if self._pump_task is not None:
            return
        self._pump_task = asyncio.create_task(self._pump_loop())

    async def _pump_loop(self) -> None:
        try:
            while self.term.alive():
                data = await asyncio.to_thread(self.term.read)
                if data:
                    self._append_scrollback(data)
                    ws = self._ws
                    if ws is not None and ws.client_state == WebSocketState.CONNECTED:
                        try:
                            await ws.send_bytes(data)
                        except Exception:
                            pass
                else:
                    await asyncio.sleep(0.02)
            data = await asyncio.to_thread(self.term.read)
            if data:
                self._append_scrollback(data)
                ws = self._ws
                if ws is not None and ws.client_state == WebSocketState.CONNECTED:
                    try:
                        await ws.send_bytes(data)
                    except Exception:
                        pass
            ws = self._ws
            if ws is not None and ws.client_state == WebSocketState.CONNECTED:
                code = self.term.proc.returncode if self.term.proc is not None else None
                try:
                    await ws.send_text(json.dumps({"t": "exit", "code": code}))
                except Exception:
                    pass
        finally:
            async with _sessions_lock:
                _managed_sessions.pop(self.session_id, None)
            await asyncio.to_thread(self.term.close)

    async def attach(self, ws: WebSocket) -> None:
        self._ws = ws
        self.detached_at = None

    async def detach(self) -> None:
        if self.explicit_close:
            return
        self._ws = None
        self.detached_at = time.monotonic()

    async def request_close(self) -> None:
        """Kill this shell and drop it so a later disconnect cannot reattach."""
        if self.explicit_close:
            return
        self.explicit_close = True
        self._ws = None
        self.detached_at = None
        async with _sessions_lock:
            _managed_sessions.pop(self.session_id, None)
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()
            try:
                await self._pump_task
            except asyncio.CancelledError:
                pass
            self._pump_task = None
        await asyncio.to_thread(self.term.close)

    async def send_ready(self, ws: WebSocket, *, reattached: bool) -> None:
        await ws.send_text(
            json.dumps(
                {
                    "t": "ready",
                    "session_id": self.session_id,
                    "cwd": str(host_workspace()),
                    "reattached": reattached,
                    "max_sessions": MAX_SESSIONS,
                }
            )
        )
        if self.scrollback:
            await ws.send_bytes(bytes(self.scrollback))

    def close(self) -> None:
        _managed_sessions.pop(self.session_id, None)
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()
        self._pump_task = None
        self.term.close()


def _prune_managed_sessions() -> None:
    now = time.monotonic()
    for session_id, managed in list(_managed_sessions.items()):
        if not managed.alive():
            managed.close()
            _managed_sessions.pop(session_id, None)
            continue
        if (
            managed._ws is None
            and managed.detached_at is not None
            and now - managed.detached_at > DETACHED_TTL_SEC
        ):
            managed.close()
            _managed_sessions.pop(session_id, None)


async def _get_or_create_managed_session(
    session_id: Optional[str],
    spawn: SpawnFactory,
) -> tuple[ManagedTerminalSession, bool]:
    """Return (session, reattached). Raises RuntimeError when at capacity."""
    _prune_managed_sessions()
    reattached = False
    managed: Optional[ManagedTerminalSession] = None
    if session_id:
        managed = _managed_sessions.get(session_id)
        if managed is not None and not managed.alive():
            managed.close()
            _managed_sessions.pop(session_id, None)
            managed = None
        elif managed is not None:
            reattached = True
    if managed is None:
        if len(_managed_sessions) >= MAX_SESSIONS:
            raise RuntimeError(f"Too many terminal sessions (max {MAX_SESSIONS})")
        term = spawn(cols=DEFAULT_COLS, rows=DEFAULT_ROWS)
        managed = ManagedTerminalSession(term)
        _managed_sessions[managed.session_id] = managed
        await managed.start_pump()
    return managed, reattached


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
    """Accept, authenticate, attach to a persistent PTY, and bridge bytes."""
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

    requested_id = ws.query_params.get("session")
    managed: Optional[ManagedTerminalSession] = None
    try:
        async with _sessions_lock:
            try:
                managed, reattached = await _get_or_create_managed_session(
                    requested_id,
                    spawn,
                )
            except RuntimeError as exc:
                await ws.send_text(json.dumps({"t": "error", "message": str(exc)}))
                await ws.close(code=4403)
                return
            except Exception as exc:  # noqa: BLE001 — surface spawn failures to UI
                await ws.send_text(
                    json.dumps({"t": "error", "message": str(exc) or "failed to start shell"})
                )
                await ws.close(code=4400)
                return
        await managed.attach(ws)
        await managed.send_ready(ws, reattached=reattached)

        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                managed.term.write(message["bytes"])
                continue
            text = message.get("text")
            if text is None:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                managed.term.write(text.encode("utf-8", errors="replace"))
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("t") == "close":
                await managed.request_close()
                break
            if payload.get("t") == "resize":
                try:
                    managed.term.resize(
                        int(payload.get("cols", DEFAULT_COLS)),
                        int(payload.get("rows", DEFAULT_ROWS)),
                    )
                except (TypeError, ValueError):
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        if managed is not None:
            await managed.detach()


def reset_session_counter_for_tests() -> None:
    for managed in list(_managed_sessions.values()):
        managed.close()
    _managed_sessions.clear()
