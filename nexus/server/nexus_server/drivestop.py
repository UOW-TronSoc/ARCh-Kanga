"""Latest /drivestop sample shared by every browser."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Optional


@dataclass(frozen=True)
class DrivestopObservation:
    ros_available: bool
    whs_available: bool
    drivestop: Optional[bool]


class DrivestopStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ros_available = False
        self._whs_available = False
        self._drivestop: Optional[bool] = None

    def read(self) -> DrivestopObservation:
        with self._lock:
            return DrivestopObservation(self._ros_available, self._whs_available, self._drivestop)

    def set_ros_available(self, available: bool) -> None:
        with self._lock:
            self._ros_available = available

    def observe(self, drivestop: bool, publisher_count: int) -> None:
        with self._lock:
            self._drivestop = bool(drivestop)
            self._whs_available = publisher_count > 0

    def set_publisher_count(self, publisher_count: int) -> None:
        with self._lock:
            self._whs_available = publisher_count > 0
