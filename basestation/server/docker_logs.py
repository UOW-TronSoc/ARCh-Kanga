"""Follow PID-1 `docker logs` for basestation and onboard containers."""

from __future__ import annotations

import os
import re
import threading
from collections import deque
from typing import Any, Callable, Optional

from .rosout_buffer import (
    DEFAULT_MAX_RECORDS,
    HTTP_LEVEL_VALUES,
    ROS_LOG_INFO,
    ros_level_name,
)

LEAVES = ("basestation", "onboard")
DEFAULT_BASESTATION_NAME = "basestation-server"
# Prefer the production runtime when both exist: kanga-dev is usually
# `sleep infinity`, so its docker logs are empty while kanga-onboard is PID-1
# launch-agent stdout.
ONBOARD_CANDIDATES = ("kanga-onboard", "kanga-dev")
RETRY_SECONDS = 5.0

_TS_PREFIX = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?)\s+(?P<body>.*)$"
)
_RCL_LEVEL = re.compile(r"\[(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]")
_RCL_LOGGER = re.compile(
    r"\[(?:DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]"
    r"(?:\s+\[[^\]]+\])?"
    r"\s+\[(?P<name>[^\]]+)\]:"
)


def parse_docker_log_line(raw: str, container_name: str = "") -> dict[str, Any]:
    """Turn one `docker logs --timestamps` line into a pane record (no seq)."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    text = raw.rstrip("\r\n")
    stamp = ""
    body = text
    match = _TS_PREFIX.match(text)
    if match:
        stamp = match.group("stamp")
        body = match.group("body")
    level = ROS_LOG_INFO
    level_token = _RCL_LEVEL.search(body)
    if level_token:
        level = HTTP_LEVEL_VALUES.get(level_token.group("level").upper(), ROS_LOG_INFO)
    name = container_name
    logger = _RCL_LOGGER.search(body)
    if logger:
        name = logger.group("name").strip() or container_name
    return {
        "stamp": stamp,
        "level": int(level),
        "level_name": ros_level_name(int(level)),
        "name": name or "",
        "msg": body,
    }


def configured_basestation_name() -> str:
    return os.environ.get("KANGA_DOCKER_BASESTATION_NAME", DEFAULT_BASESTATION_NAME).strip() or (
        DEFAULT_BASESTATION_NAME
    )


def configured_onboard_name() -> str:
    return os.environ.get("KANGA_DOCKER_ONBOARD_NAME", "").strip()


def resolve_onboard_name(exists: Callable[[str], bool]) -> str:
    pinned = configured_onboard_name()
    if pinned:
        return pinned
    for name in ONBOARD_CANDIDATES:
        if exists(name):
            return name
    return ONBOARD_CANDIDATES[0]


class DockerLogBuffer:
    def __init__(self, max_records: int = DEFAULT_MAX_RECORDS) -> None:
        self._lock = threading.Lock()
        self._records: deque[dict[str, Any]] = deque(maxlen=max_records)
        self._next_seq = 1

    def append_line(self, raw: str, container_name: str) -> dict[str, Any]:
        parsed = parse_docker_log_line(raw, container_name)
        with self._lock:
            record = {
                "seq": self._next_seq,
                **parsed,
            }
            self._next_seq += 1
            self._records.append(record)
            return record

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


class DockerLogStore:
    """Always-on followers for the two Docker leaves."""

    def __init__(
        self,
        *,
        client_factory: Optional[Callable[[], Any]] = None,
        retry_seconds: float = RETRY_SECONDS,
    ) -> None:
        self._client_factory = client_factory or _docker_from_env
        self._retry_seconds = retry_seconds
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self.buffers = {leaf: DockerLogBuffer() for leaf in LEAVES}
        self._status = {leaf: "idle" for leaf in LEAVES}
        self._container = {
            "basestation": configured_basestation_name(),
            "onboard": configured_onboard_name() or ONBOARD_CANDIDATES[0],
        }

    def start(self) -> None:
        if self._threads:
            return
        self._stop.clear()
        for leaf in LEAVES:
            thread = threading.Thread(
                target=self._follow_loop,
                args=(leaf,),
                name=f"docker-logs-{leaf}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._threads.clear()

    def snapshot(self, leaf: str) -> dict[str, Any]:
        self._require_leaf(leaf)
        with self._lock:
            container = self._container[leaf]
            status = self._status[leaf]
        return {
            "leaf": leaf,
            "container": container,
            "status": status,
            "records": self.buffers[leaf].snapshot(),
        }

    def clear(self, leaf: str) -> None:
        self._require_leaf(leaf)
        self.buffers[leaf].clear()

    def append_line(self, leaf: str, raw: str, container_name: str = "") -> dict[str, Any]:
        """Test helper: ingest a line without Docker."""
        self._require_leaf(leaf)
        name = container_name or self._container[leaf]
        return self.buffers[leaf].append_line(raw, name)

    def _require_leaf(self, leaf: str) -> None:
        if leaf not in LEAVES:
            raise ValueError(f"unknown docker log leaf: {leaf}")

    def _set_status(self, leaf: str, status: str, container: Optional[str] = None) -> None:
        with self._lock:
            self._status[leaf] = status
            if container is not None:
                self._container[leaf] = container

    def _follow_loop(self, leaf: str) -> None:
        while not self._stop.is_set():
            try:
                client = self._client_factory()
            except Exception as exc:  # noqa: BLE001 — socket missing is normal in tests
                self._set_status(leaf, f"docker unavailable: {exc}")
                self._stop.wait(self._retry_seconds)
                continue
            name = self._target_name(leaf, client)
            self._set_status(leaf, "connecting", name)
            try:
                container = client.containers.get(name)
                stream = container.logs(
                    stream=True,
                    follow=True,
                    timestamps=True,
                    stdout=True,
                    stderr=True,
                )
                self._set_status(leaf, "live", name)
                watchdog = threading.Thread(
                    target=self._abort_follow_if_target_changes,
                    args=(leaf, name, stream, client),
                    name=f"docker-logs-upgrade-{leaf}",
                    daemon=True,
                )
                watchdog.start()
                self._consume_stream(leaf, name, stream)
            except Exception as exc:  # noqa: BLE001 — missing container, API errors
                status = _status_for_docker_error(exc, name)
                self._set_status(leaf, status, name)
            self._stop.wait(self._retry_seconds)

    def _target_name(self, leaf: str, client: Any) -> str:
        if leaf == "basestation":
            return configured_basestation_name()
        return resolve_onboard_name(lambda candidate: _container_exists(client, candidate))

    def _abort_follow_if_target_changes(
        self, leaf: str, name: str, stream: Any, client: Any
    ) -> None:
        """Silent kanga-dev follow never yields; re-resolve so kanga-onboard can win."""
        while not self._stop.wait(self._retry_seconds):
            try:
                better = self._target_name(leaf, client)
            except Exception:  # noqa: BLE001
                continue
            if better == name:
                continue
            close = getattr(stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass
            return

    def _consume_stream(self, leaf: str, name: str, stream: Any) -> None:
        pending = ""
        try:
            for chunk in stream:
                if self._stop.is_set():
                    break
                pending += _chunk_to_text(chunk)
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    if line:
                        self.buffers[leaf].append_line(line, name)
            if pending.strip():
                self.buffers[leaf].append_line(pending, name)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass


def _chunk_to_text(chunk: Any) -> str:
    if isinstance(chunk, bytes):
        return chunk.decode("utf-8", errors="replace")
    return str(chunk)


def _container_exists(client: Any, name: str) -> bool:
    try:
        container = client.containers.get(name)
        status = getattr(container, "status", "running")
        return status == "running"
    except Exception:  # noqa: BLE001 — NotFound or API down
        return False


def _status_for_docker_error(exc: BaseException, name: str) -> str:
    kind = type(exc).__name__
    if kind in ("NotFound", "APIError") or "not found" in str(exc).lower():
        return f"missing container: {name}"
    return f"follow failed: {exc}"


def _docker_from_env() -> Any:
    import docker

    return docker.from_env()
