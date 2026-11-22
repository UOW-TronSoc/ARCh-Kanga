"""Health separates a reachable web server from ROS initialisation."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from nexus_server.ros_runtime import RosStatus


class RosHealth(BaseModel):
    initialized: bool
    error: Optional[str] = None


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    backend: Literal["available"] = "available"
    ros: RosHealth


def build_health(ros_status: RosStatus) -> HealthReport:
    return HealthReport(
        status="ok" if ros_status.initialized else "degraded",
        backend="available",
        ros=RosHealth(initialized=ros_status.initialized, error=ros_status.error),
    )
