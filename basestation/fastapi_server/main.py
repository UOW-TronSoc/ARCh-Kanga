"""Stub cmd_vel FastAPI on port 8080 — health plus optional Twist publisher."""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

from fastapi import FastAPI

app = FastAPI(title="basestation-fastapi-stub", version="0.0.0")

_cmd_vel_node: Any = None
_ros_ready = False
_ros_error: Optional[str] = None


def _try_start_cmd_vel_publisher() -> None:
    global _cmd_vel_node, _ros_ready, _ros_error
    try:
        import rclpy
        from geometry_msgs.msg import Twist
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node

        class CmdVelPublisher(Node):
            def __init__(self) -> None:
                super().__init__("basestation_stub_cmd_vel")
                self.publisher = self.create_publisher(Twist, "/cmd_vel", 10)
                self.get_logger().info("Stub CmdVelPublisher ready on /cmd_vel")

            def publish_zero(self) -> None:
                self.publisher.publish(Twist())

        if not rclpy.ok():
            rclpy.init()

        node = CmdVelPublisher()
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        def spin() -> None:
            executor.spin()

        thread = threading.Thread(target=spin, daemon=True)
        thread.start()
        _cmd_vel_node = node
        _ros_ready = True
    except Exception as exc:  # noqa: BLE001 — stub stays up even if ROS fails
        _ros_error = str(exc)
        _ros_ready = False


@app.on_event("startup")
def on_startup() -> None:
    _try_start_cmd_vel_publisher()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _ros_error is None else "degraded",
        "service": "basestation-fastapi",
        "role": "stub",
        "cmd_vel_publisher": _ros_ready,
        "error": _ros_error,
        "workspace_sourced": os.path.isdir("/workspace/install"),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
    }


@app.post("/cmd_vel/zero")
def publish_zero() -> dict:
    if _cmd_vel_node is None:
        return {"status": "unavailable", "detail": _ros_error or "ROS node not started"}
    _cmd_vel_node.publish_zero()
    return {"status": "published", "topic": "/cmd_vel"}
