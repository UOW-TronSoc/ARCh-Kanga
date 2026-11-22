"""One ROS client for the NEXUS process."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Callable, Optional


@dataclass(frozen=True)
class RosStatus:
    initialized: bool
    error: Optional[str] = None


class RosRuntime:
    def __init__(self) -> None:
        self._status = RosStatus(initialized=False)
        self._node = None
        self._executor = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._configurators: list[Callable[[object], None]] = []

    def add_configurator(self, configurator: Callable[[object], None]) -> None:
        self._configurators.append(configurator)

    def status(self) -> RosStatus:
        with self._lock:
            return self._status

    def start(self) -> None:
        try:
            self._start_rclpy()
        except Exception as exc:  # noqa: BLE001 - init failure stays on /health
            self._set_status(False, f"{type(exc).__name__}: {exc}")

    def stop(self) -> None:
        executor = self._executor
        node = self._node
        thread = self._thread
        if executor is not None:
            executor.shutdown()
        if node is not None:
            node.destroy_node()
        try:
            import rclpy

            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        self._executor = None
        self._node = None
        self._thread = None

    def _start_rclpy(self) -> None:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node

        if not rclpy.ok():
            rclpy.init()
        node = Node("nexus_basestation")
        for configurator in self._configurators:
            configurator(node)
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        thread = threading.Thread(target=self._spin, args=(executor,), name="nexus-ros", daemon=True)
        self._node = node
        self._executor = executor
        self._thread = thread
        thread.start()
        self._set_status(True, None)

    def _spin(self, executor: object) -> None:
        try:
            executor.spin()
        except Exception as exc:  # noqa: BLE001
            self._set_status(False, f"ROS executor stopped: {exc}")

    def _set_status(self, initialized: bool, error: Optional[str]) -> None:
        with self._lock:
            self._status = RosStatus(initialized=initialized, error=error)


class StaticRosRuntime:
    def __init__(self, initialized: bool = False, error: Optional[str] = None) -> None:
        self._status = RosStatus(initialized=initialized, error=error)
        self.started = False

    def add_configurator(self, configurator: Callable[[object], None]) -> None:
        del configurator

    def status(self) -> RosStatus:
        return self._status

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        return None
