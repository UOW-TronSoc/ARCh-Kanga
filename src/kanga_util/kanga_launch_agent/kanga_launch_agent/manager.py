"""Thread-safe ownership of fixed ROS launch processes."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable, Mapping, Optional, Sequence

from .profiles import PROFILES, LaunchProfile


class SystemState(str, Enum):
    STOPPED = "STOPPED"
    UNMANAGED = "UNMANAGED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class LaunchManagerError(RuntimeError):
    """Base class for expected launch-manager failures."""


class UnknownSystem(LaunchManagerError):
    pass


class InvalidTransition(LaunchManagerError):
    pass


class LaunchUnavailable(LaunchManagerError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signal_process_group(
    process: subprocess.Popen, sig: signal.Signals
) -> None:
    os.killpg(os.getpgid(process.pid), sig)


class LaunchManager:
    """Lifecycle manager for fixed profiles running in this container."""

    def __init__(
        self,
        node_names: Callable[[], Iterable[str]],
        *,
        profiles: Sequence[LaunchProfile] = PROFILES,
        startup_grace_seconds: float = 3.0,
        shutdown_timeout_seconds: float = 10.0,
        terminate_timeout_seconds: float = 5.0,
        kill_timeout_seconds: float = 2.0,
        discovery_settle_seconds: float = 3.0,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        executable_finder: Callable[[str], Optional[str]] = shutil.which,
        process_group_signal: Callable[
            [subprocess.Popen, signal.Signals], None
        ] = _signal_process_group,
    ) -> None:
        if not profiles:
            raise ValueError("at least one launch profile is required")
        self._profiles: Mapping[str, LaunchProfile] = {
            profile.system_id: profile for profile in profiles
        }
        if len(self._profiles) != len(profiles):
            raise ValueError("launch profile ids must be unique")

        self._node_names = node_names
        self._startup_grace_seconds = startup_grace_seconds
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._terminate_timeout_seconds = terminate_timeout_seconds
        self._kill_timeout_seconds = kill_timeout_seconds
        self._discovery_settle_seconds = discovery_settle_seconds
        self._popen = popen
        self._executable_finder = executable_finder
        self._process_group_signal = process_group_signal

        self._lock = threading.RLock()
        self._state = {
            profile.system_id: SystemState.STOPPED for profile in profiles
        }
        self._processes: dict[str, subprocess.Popen] = {}
        self._generations = {profile.system_id: 0 for profile in profiles}
        self._startup_timers: dict[str, threading.Timer] = {}
        self._started_at: dict[str, Optional[str]] = {
            profile.system_id: None for profile in profiles
        }
        now = _utc_now()
        self._transitioned_at = {
            profile.system_id: now for profile in profiles
        }
        self._exit_codes: dict[str, Optional[int]] = {
            profile.system_id: None for profile in profiles
        }
        self._last_errors: dict[str, Optional[str]] = {
            profile.system_id: None for profile in profiles
        }
        self._ignore_external_until = {
            profile.system_id: 0.0 for profile in profiles
        }

    def _profile(self, system_id: str) -> LaunchProfile:
        try:
            return self._profiles[system_id]
        except KeyError as exc:
            raise UnknownSystem(f"unknown system {system_id!r}") from exc

    def _transition(
        self,
        system_id: str,
        state: SystemState,
        *,
        error: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        self._state[system_id] = state
        self._transitioned_at[system_id] = _utc_now()
        self._last_errors[system_id] = error
        self._exit_codes[system_id] = exit_code

    def _external_nodes(
        self, profile: LaunchProfile, *, strict: bool = False
    ) -> set[str]:
        try:
            discovered = set(self._node_names())
        except Exception as exc:
            if strict:
                raise LaunchUnavailable(
                    "ROS discovery is unavailable; cannot verify launch "
                    "ownership"
                ) from exc
            return set()
        return profile.sentinel_nodes.intersection(discovered)

    def _refresh_external_state(
        self, profile: LaunchProfile, *, strict: bool = False
    ) -> None:
        system_id = profile.system_id
        if system_id in self._processes:
            return
        if time.monotonic() < self._ignore_external_until[system_id]:
            return

        external = self._external_nodes(profile, strict=strict)
        state = self._state[system_id]
        if external and state in {
            SystemState.STOPPED,
            SystemState.FAILED,
            SystemState.UNMANAGED,
        }:
            if state is not SystemState.UNMANAGED:
                self._transition(system_id, SystemState.UNMANAGED)
        elif not external and state is SystemState.UNMANAGED:
            self._transition(system_id, SystemState.STOPPED)

    def _is_available(self, profile: LaunchProfile) -> bool:
        return self._executable_finder(profile.command[0]) is not None

    @staticmethod
    def _allowed_actions(state: SystemState) -> list[str]:
        if state in {SystemState.STOPPED, SystemState.FAILED}:
            return ["start"]
        if state is SystemState.STARTING:
            return ["stop"]
        if state is SystemState.RUNNING:
            return ["stop", "restart"]
        return []

    def status(self, system_id: str) -> dict:
        profile = self._profile(system_id)
        with self._lock:
            self._refresh_external_state(profile)
            state = self._state[system_id]
            return {
                "id": profile.system_id,
                "label": profile.label,
                "available": self._is_available(profile),
                "state": state.value,
                "health": "NOT_CHECKED",
                "owned": system_id in self._processes,
                "allowed_actions": self._allowed_actions(state),
                "started_at": self._started_at[system_id],
                "transitioned_at": self._transitioned_at[system_id],
                "exit_code": self._exit_codes[system_id],
                "last_error": self._last_errors[system_id],
            }

    def statuses(self) -> list[dict]:
        return [self.status(system_id) for system_id in self._profiles]

    def start(self, system_id: str) -> dict:
        profile = self._profile(system_id)
        with self._lock:
            self._refresh_external_state(profile, strict=True)
            state = self._state[system_id]
            if state not in {SystemState.STOPPED, SystemState.FAILED}:
                raise InvalidTransition(
                    f"cannot start {system_id} while it is {state.value}"
                )
            if not self._is_available(profile):
                raise LaunchUnavailable(
                    f"launch executable {profile.command[0]!r} is unavailable"
                )

            self._generations[system_id] += 1
            generation = self._generations[system_id]
            self._started_at[system_id] = _utc_now()
            self._transition(system_id, SystemState.STARTING)
            try:
                process = self._popen(
                    list(profile.command), start_new_session=True
                )
            except OSError as exc:
                self._started_at[system_id] = None
                self._transition(
                    system_id,
                    SystemState.FAILED,
                    error=f"failed to start launch process: {exc}",
                )
                raise LaunchUnavailable(str(exc)) from exc

            self._processes[system_id] = process
            timer = threading.Timer(
                self._startup_grace_seconds,
                self._mark_running,
                args=(system_id, generation, process),
            )
            timer.daemon = True
            self._startup_timers[system_id] = timer
            timer.start()
            monitor = threading.Thread(
                target=self._monitor_process,
                args=(system_id, generation, process),
                name=f"launch-monitor-{system_id}",
                daemon=True,
            )
            monitor.start()
            return self.status(system_id)

    def _mark_running(
        self,
        system_id: str,
        generation: int,
        process: subprocess.Popen,
    ) -> None:
        with self._lock:
            if (
                self._generations[system_id] == generation
                and self._processes.get(system_id) is process
                and self._state[system_id] is SystemState.STARTING
                and process.poll() is None
            ):
                self._transition(system_id, SystemState.RUNNING)

    def _monitor_process(
        self,
        system_id: str,
        generation: int,
        process: subprocess.Popen,
    ) -> None:
        while process.poll() is None:
            time.sleep(0.1)
        return_code = process.poll()

        with self._lock:
            if (
                self._generations[system_id] != generation
                or self._processes.get(system_id) is not process
            ):
                return
            timer = self._startup_timers.pop(system_id, None)
            if timer is not None:
                timer.cancel()
            self._processes.pop(system_id, None)
            if self._state[system_id] is SystemState.STOPPING:
                self._transition(
                    system_id, SystemState.STOPPED, exit_code=return_code
                )
                self._ignore_external_until[system_id] = (
                    time.monotonic() + self._discovery_settle_seconds
                )
            else:
                self._transition(
                    system_id,
                    SystemState.FAILED,
                    error=(
                        "launch process exited unexpectedly "
                        f"({return_code})"
                    ),
                    exit_code=return_code,
                )

    def stop(self, system_id: str) -> dict:
        profile = self._profile(system_id)
        with self._lock:
            self._refresh_external_state(profile)
            state = self._state[system_id]
            if state not in {SystemState.STARTING, SystemState.RUNNING}:
                raise InvalidTransition(
                    f"cannot stop {system_id} while it is {state.value}"
                )
            process = self._processes[system_id]
            timer = self._startup_timers.pop(system_id, None)
            if timer is not None:
                timer.cancel()
            self._transition(system_id, SystemState.STOPPING)

        return_code: Optional[int] = None
        try:
            self._process_group_signal(process, signal.SIGINT)
            return_code = process.wait(timeout=self._shutdown_timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                self._process_group_signal(process, signal.SIGTERM)
                return_code = process.wait(
                    timeout=self._terminate_timeout_seconds
                )
            except subprocess.TimeoutExpired:
                self._process_group_signal(process, signal.SIGKILL)
                try:
                    return_code = process.wait(
                        timeout=self._kill_timeout_seconds
                    )
                except subprocess.TimeoutExpired as exc:
                    with self._lock:
                        self._transition(
                            system_id,
                            SystemState.FAILED,
                            error="launch process did not exit after SIGKILL",
                        )
                    raise LaunchManagerError(
                        "launch process did not exit after SIGKILL"
                    ) from exc
        except ProcessLookupError:
            return_code = process.poll()

        with self._lock:
            if self._processes.get(system_id) is process:
                self._processes.pop(system_id, None)
                self._transition(
                    system_id, SystemState.STOPPED, exit_code=return_code
                )
                self._ignore_external_until[system_id] = (
                    time.monotonic() + self._discovery_settle_seconds
                )
            return self.status(system_id)

    def restart(self, system_id: str) -> dict:
        with self._lock:
            profile = self._profile(system_id)
            self._refresh_external_state(profile)
            if self._state[system_id] is not SystemState.RUNNING:
                raise InvalidTransition(
                    f"cannot restart {system_id} while it is "
                    f"{self._state[system_id].value}"
                )
        self.stop(system_id)
        return self.start(system_id)

    def shutdown(self) -> None:
        """Best-effort termination of every process owned by this agent."""
        for system_id in self._profiles:
            with self._lock:
                state = self._state[system_id]
            if state in {SystemState.STARTING, SystemState.RUNNING}:
                try:
                    self.stop(system_id)
                except Exception:  # noqa: BLE001 - continue agent teardown
                    pass
