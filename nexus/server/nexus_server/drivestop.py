"""Latest /drivestop sample shared by every browser."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Optional

WHEEL_STALE_SECONDS = 1.0


@dataclass(frozen=True)
class WheelVelocity:
    name: str
    velocity: float


@dataclass(frozen=True)
class DrivestopObservation:
    ros_available: bool
    whs_available: bool
    drivestop: Optional[bool]
    mode_available: bool = False
    closed_loop: Optional[bool] = None
    wheels_available: bool = False
    wheels: tuple[WheelVelocity, ...] = ()
    wheels_freshness: str = "unavailable"
    drivestop_generation: int = 0
    mode_generation: int = 0


class DrivestopStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ros_available = False
        self._whs_available = False
        self._drivestop: Optional[bool] = None
        self._mode_available = False
        self._closed_loop: Optional[bool] = None
        self._wheels_available = False
        self._wheels: tuple[WheelVelocity, ...] = ()
        self._wheels_at: Optional[float] = None
        self._drivestop_generation = 0
        self._mode_generation = 0

    def read(self) -> DrivestopObservation:
        with self._lock:
            return DrivestopObservation(
                self._ros_available,
                self._whs_available,
                self._drivestop,
                self._mode_available,
                self._closed_loop,
                self._wheels_available,
                self._wheels,
                self._wheel_freshness_locked(),
                self._drivestop_generation,
                self._mode_generation,
            )

    def set_ros_available(self, available: bool) -> None:
        with self._lock:
            self._ros_available = available

    def observe(self, drivestop: bool, publisher_count: int) -> None:
        with self._lock:
            self._drivestop = bool(drivestop)
            self._whs_available = publisher_count > 0
            self._drivestop_generation += 1

    def set_publisher_count(self, publisher_count: int) -> None:
        with self._lock:
            self._whs_available = publisher_count > 0

    def observe_mode(self, closed_loop: bool, publisher_count: int) -> None:
        with self._lock:
            self._closed_loop = bool(closed_loop)
            self._mode_available = publisher_count > 0
            self._mode_generation += 1

    def set_mode_publisher_count(self, publisher_count: int) -> None:
        with self._lock:
            self._mode_available = publisher_count > 0
            if publisher_count <= 0:
                self._closed_loop = None

    def observe_wheels(self, wheels: list[tuple[str, float]]) -> None:
        with self._lock:
            self._wheels = tuple(WheelVelocity(name, velocity) for name, velocity in wheels)
            self._wheels_available = True
            self._wheels_at = time.monotonic()

    def age_wheels(self, seconds: float) -> None:
        with self._lock:
            if self._wheels_at is not None:
                self._wheels_at -= seconds

    def _wheel_freshness_locked(self) -> str:
        if self._wheels_at is None:
            return "unavailable"
        if time.monotonic() - self._wheels_at > WHEEL_STALE_SECONDS:
            return "stale"
        return "fresh"
