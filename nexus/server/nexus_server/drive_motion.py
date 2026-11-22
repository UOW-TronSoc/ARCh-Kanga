"""Scale and publish /core/cmd_vel. A quiet operator is stopped here."""

from __future__ import annotations

import math
import os
import threading
import time
from typing import Callable, Optional

MAX_LINEAR_MPS = float(os.environ.get("NEXUS_MAX_LINEAR_MPS", "0.3"))
MAX_YAW_RAD_S = float(os.environ.get("NEXUS_MAX_YAW_RAD_S", "0.3"))
WATCHDOG_SECONDS = 0.4


def speed_factor(scale_pct: float) -> float:
    """0–90% reaches full output. 90–100% stays at full output."""
    scale = max(0.0, min(100.0, scale_pct))
    if scale >= 90.0:
        return 1.0
    return scale / 90.0


class MotionPublisher:
    def __init__(self, on_expire: Optional[Callable[[], None]] = None) -> None:
        self._on_expire = on_expire
        self._lock = threading.Lock()
        self._x = 0.0
        self._yaw = 0.0
        self._scale = 0.0
        self._stamp: Optional[float] = None
        self._active = False
        self._publisher = None
        self._sink: Optional[Callable[[float, float], None]] = None

    def set_watchdog_handler(self, handler: Optional[Callable[[], None]]) -> None:
        self._on_expire = handler

    def set_sink(self, sink: Optional[Callable[[float, float], None]]) -> None:
        self._sink = sink

    def attach(self, node: object) -> None:
        from geometry_msgs.msg import Twist

        self._publisher = node.create_publisher(Twist, "/core/cmd_vel", 10)
        node.create_timer(0.05, self.tick)

    def command(self, x: float, yaw: float, scale: float) -> None:
        with self._lock:
            self._x = max(-1.0, min(1.0, x))
            self._yaw = max(-1.0, min(1.0, yaw))
            self._scale = max(0.0, min(100.0, scale))
            self._stamp = time.monotonic()

    def zero_if_active(self) -> None:
        with self._lock:
            was_active = self._active or self._stamp is not None
            self._stamp = None
            self._x = 0.0
            self._yaw = 0.0
            self._scale = 0.0
            self._active = False
            if was_active:
                self._publish(0.0, 0.0)

    def tick(self) -> None:
        expired = False
        with self._lock:
            if self._stamp is None:
                return
            if time.monotonic() - self._stamp > WATCHDOG_SECONDS:
                self._stamp = None
                self._x = 0.0
                self._yaw = 0.0
                self._scale = 0.0
                self._active = False
                self._publish(0.0, 0.0)
                expired = True
            else:
                factor = speed_factor(self._scale)
                self._publish(self._x * factor * MAX_LINEAR_MPS, self._yaw * factor * MAX_YAW_RAD_S)
                self._active = True
        if expired and self._on_expire is not None:
            self._on_expire()

    def _publish(self, linear: float, yaw: float) -> None:
        if self._sink is not None:
            self._sink(linear, yaw)
            return
        if self._publisher is None:
            return
        from geometry_msgs.msg import Twist

        message = Twist()
        message.linear.x = linear
        message.angular.z = yaw
        self._publisher.publish(message)


def finite_drive(x: object, yaw: object, scale: object) -> bool:
    return all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in (x, yaw, scale))
