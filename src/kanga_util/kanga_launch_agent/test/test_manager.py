"""Unit tests for the onboard allowlisted launch lifecycle manager."""

from __future__ import annotations

import signal
import subprocess
import time

import pytest

from kanga_launch_agent.manager import (
    InvalidTransition,
    LaunchManager,
    LaunchUnavailable,
)
from kanga_launch_agent.profiles import CORE_PROFILE


class FakeProcess:
    _next_pid = 1000

    def __init__(self, timeouts_before_exit: int = 0) -> None:
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self.returncode = None
        self.pending_signal = None
        self.timeouts_before_exit = timeouts_before_exit

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.timeouts_before_exit > 0:
            self.timeouts_before_exit -= 1
            raise subprocess.TimeoutExpired("ros2", timeout)
        if self.returncode is None and self.pending_signal is not None:
            self.returncode = -int(self.pending_signal)
        return self.returncode


class Harness:
    def __init__(self) -> None:
        self.nodes: set[str] = set()
        self.processes: list[FakeProcess] = []
        self.commands: list[tuple[list[str], bool]] = []
        self.signals: list[signal.Signals] = []

    def manager(self, *, timeouts_before_exit: int = 0) -> LaunchManager:
        def popen(command, *, start_new_session):
            process = FakeProcess(timeouts_before_exit=timeouts_before_exit)
            self.processes.append(process)
            self.commands.append((command, start_new_session))
            return process

        def signal_group(process, requested_signal):
            self.signals.append(requested_signal)
            process.pending_signal = requested_signal

        return LaunchManager(
            lambda: self.nodes,
            startup_grace_seconds=0.01,
            shutdown_timeout_seconds=0.01,
            terminate_timeout_seconds=0.01,
            kill_timeout_seconds=0.01,
            discovery_settle_seconds=0.0,
            popen=popen,
            executable_finder=lambda _name: "/opt/ros/humble/bin/ros2",
            process_group_signal=signal_group,
        )


def wait_for_state(manager: LaunchManager, expected: str) -> dict:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        status = manager.status("core")
        if status["state"] == expected:
            return status
        time.sleep(0.01)
    pytest.fail(f"core did not reach {expected}: {manager.status('core')}")


def test_core_profile_is_fixed_and_starts_in_own_session() -> None:
    harness = Harness()
    manager = harness.manager()
    status = manager.start("core")

    assert status["state"] == "STARTING"
    assert harness.commands == [(list(CORE_PROFILE.command), True)]
    assert "shell" not in CORE_PROFILE.command
    running = wait_for_state(manager, "RUNNING")
    assert running["health"] == "NOT_CHECKED"
    assert running["allowed_actions"] == ["stop", "restart"]
    manager.shutdown()


def test_external_sentinel_is_unmanaged_and_cannot_be_started() -> None:
    harness = Harness()
    harness.nodes.add("/suspension_joint_state_publisher")
    manager = harness.manager()

    status = manager.status("core")
    assert status["state"] == "UNMANAGED"
    assert not status["owned"]
    assert status["allowed_actions"] == []
    with pytest.raises(InvalidTransition):
        manager.start("core")

    harness.nodes.clear()
    assert manager.status("core")["state"] == "STOPPED"


def test_unexpected_exit_becomes_failed_and_can_be_started_again() -> None:
    harness = Harness()
    manager = harness.manager()
    manager.start("core")
    harness.processes[-1].returncode = 7

    failed = wait_for_state(manager, "FAILED")
    assert failed["exit_code"] == 7
    assert "unexpectedly" in failed["last_error"]
    assert failed["allowed_actions"] == ["start"]

    manager.start("core")
    assert len(harness.processes) == 2
    manager.shutdown()


def test_stop_escalates_from_sigint_to_sigterm() -> None:
    harness = Harness()
    manager = harness.manager(timeouts_before_exit=1)
    manager.start("core")
    wait_for_state(manager, "RUNNING")

    stopped = manager.stop("core")

    assert harness.signals == [signal.SIGINT, signal.SIGTERM]
    assert stopped["state"] == "STOPPED"
    assert not stopped["owned"]


def test_restart_requires_running_and_creates_a_new_process() -> None:
    harness = Harness()
    manager = harness.manager()
    with pytest.raises(InvalidTransition):
        manager.restart("core")

    manager.start("core")
    wait_for_state(manager, "RUNNING")
    status = manager.restart("core")

    assert status["state"] == "STARTING"
    assert len(harness.processes) == 2
    assert harness.signals == [signal.SIGINT]
    manager.shutdown()


def test_missing_ros2_marks_profile_unavailable() -> None:
    manager = LaunchManager(
        lambda: set(), executable_finder=lambda _name: None
    )
    assert not manager.status("core")["available"]
    with pytest.raises(LaunchUnavailable):
        manager.start("core")


def test_start_refuses_when_ros_discovery_is_unavailable() -> None:
    def unavailable_nodes():
        raise RuntimeError("rclpy unavailable")

    manager = LaunchManager(
        unavailable_nodes,
        executable_finder=lambda _name: "/opt/ros/humble/bin/ros2",
    )
    assert manager.status("core")["state"] == "STOPPED"
    with pytest.raises(LaunchUnavailable, match="discovery"):
        manager.start("core")
