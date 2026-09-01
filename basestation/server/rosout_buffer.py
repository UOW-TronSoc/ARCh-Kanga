"""In-memory /rosout ring and JSON serialization (no rclpy import)."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

# rcl_interfaces/msg/Log.msg
ROS_LOG_DEBUG = 10
ROS_LOG_INFO = 20
ROS_LOG_WARN = 30
ROS_LOG_ERROR = 40
ROS_LOG_FATAL = 50

LEVEL_NAMES = {
    ROS_LOG_DEBUG: "DEBUG",
    ROS_LOG_INFO: "INFO",
    ROS_LOG_WARN: "WARN",
    ROS_LOG_ERROR: "ERROR",
    ROS_LOG_FATAL: "FATAL",
}

HTTP_LEVEL_VALUES = {
    "DEBUG": ROS_LOG_DEBUG,
    "INFO": ROS_LOG_INFO,
    "WARNING": ROS_LOG_WARN,
    "WARN": ROS_LOG_WARN,
    "ERROR": ROS_LOG_ERROR,
    "CRITICAL": ROS_LOG_FATAL,
    "FATAL": ROS_LOG_FATAL,
}

DEFAULT_MAX_RECORDS = 4000


def ros_level_name(level: int) -> str:
    """Map an rcl numeric level to a stable UI label (floor to known values)."""
    if level >= ROS_LOG_FATAL:
        return "FATAL"
    if level >= ROS_LOG_ERROR:
        return "ERROR"
    if level >= ROS_LOG_WARN:
        return "WARN"
    if level >= ROS_LOG_INFO:
        return "INFO"
    return "DEBUG"


def http_level_value(name: str) -> int:
    return HTTP_LEVEL_VALUES.get(str(name).upper(), ROS_LOG_INFO)


def _stamp_iso(stamp_sec: int, stamp_nanosec: int) -> str:
    seconds = int(stamp_sec) + int(stamp_nanosec) / 1_000_000_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def record_from_fields(
    *,
    seq: int,
    stamp_sec: int,
    stamp_nanosec: int,
    level: int,
    name: str,
    msg: str,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "stamp": _stamp_iso(stamp_sec, stamp_nanosec),
        "level": int(level),
        "level_name": ros_level_name(int(level)),
        "name": name or "",
        "msg": msg or "",
    }


def record_from_ros_log(seq: int, msg: Any) -> dict[str, Any]:
    stamp = getattr(msg, "stamp", None)
    return record_from_fields(
        seq=seq,
        stamp_sec=int(getattr(stamp, "sec", 0) or 0),
        stamp_nanosec=int(getattr(stamp, "nanosec", 0) or 0),
        level=int(getattr(msg, "level", ROS_LOG_INFO) or ROS_LOG_INFO),
        name=str(getattr(msg, "name", "") or ""),
        msg=str(getattr(msg, "msg", "") or ""),
    )


class RosoutBuffer:
    def __init__(self, max_records: int = DEFAULT_MAX_RECORDS) -> None:
        self._lock = threading.Lock()
        self._records: deque[dict[str, Any]] = deque(maxlen=max_records)
        self._next_seq = 1

    def append_ros_log(self, msg: Any) -> dict[str, Any]:
        with self._lock:
            record = record_from_ros_log(self._next_seq, msg)
            self._next_seq += 1
            self._records.append(record)
            return record

    def append_fields(
        self,
        *,
        stamp_sec: int = 0,
        stamp_nanosec: int = 0,
        level: int = ROS_LOG_INFO,
        name: str = "",
        msg: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            record = record_from_fields(
                seq=self._next_seq,
                stamp_sec=stamp_sec,
                stamp_nanosec=stamp_nanosec,
                level=level,
                name=name,
                msg=msg,
            )
            self._next_seq += 1
            self._records.append(record)
            return record

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._records)
