"""ROS service boundary for the onboard launch manager."""

from __future__ import annotations

from typing import Iterable

import rclpy
from kanga_interfaces.msg import ManagedLaunchStatus
from kanga_interfaces.srv import ChangeManagedLaunch, ListManagedLaunches
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .manager import LaunchManager, LaunchManagerError


def _status_message(status: dict) -> ManagedLaunchStatus:
    msg = ManagedLaunchStatus()
    msg.system_id = status["id"]
    msg.label = status["label"]
    msg.state = status["state"]
    msg.health = status["health"]
    msg.available = status["available"]
    msg.owned = status["owned"]
    msg.allowed_actions = status["allowed_actions"]
    msg.started_at = status["started_at"] or ""
    msg.transitioned_at = status["transitioned_at"]
    msg.has_exit_code = status["exit_code"] is not None
    msg.exit_code = status["exit_code"] or 0
    msg.last_error = status["last_error"] or ""
    return msg


class LaunchAgentNode(Node):
    """Expose allowlisted lifecycle operations without accepting commands."""

    def __init__(self) -> None:
        super().__init__("kanga_launch_agent")
        callbacks = ReentrantCallbackGroup()
        self._manager = LaunchManager(self._node_names)
        self.create_service(
            ListManagedLaunches,
            "/launch_manager/list",
            self._list_launches,
            callback_group=callbacks,
        )
        self.create_service(
            ChangeManagedLaunch,
            "/launch_manager/change",
            self._change_launch,
            callback_group=callbacks,
        )
        self.get_logger().info("onboard launch agent ready")

    def _node_names(self) -> Iterable[str]:
        names = set()
        for name, namespace in self.get_node_names_and_namespaces():
            prefix = namespace.rstrip("/")
            names.add(f"{prefix}/{name}" if prefix else f"/{name}")
        return names

    def _list_launches(self, _request, response):
        response.success = True
        response.message = ""
        response.systems = [
            _status_message(status) for status in self._manager.statuses()
        ]
        return response

    def _change_launch(self, request, response):
        operations = {
            ChangeManagedLaunch.Request.START: self._manager.start,
            ChangeManagedLaunch.Request.STOP: self._manager.stop,
            ChangeManagedLaunch.Request.RESTART: self._manager.restart,
        }
        operation = operations.get(request.action)
        if operation is None:
            response.accepted = False
            response.message = f"unknown launch action {request.action}"
            return response

        try:
            status = operation(request.system_id)
        except LaunchManagerError as exc:
            response.accepted = False
            response.message = str(exc)
            return response
        except Exception as exc:  # noqa: BLE001 - keep agent available
            self.get_logger().error(f"launch operation failed: {exc}")
            response.accepted = False
            response.message = f"launch operation failed: {exc}"
            return response

        response.accepted = True
        response.message = ""
        response.status = _status_message(status)
        return response

    def shutdown_owned_processes(self) -> None:
        self._manager.shutdown()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LaunchAgentNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.shutdown_owned_processes()
            executor.shutdown()
            node.destroy_node()
        except KeyboardInterrupt:
            # ros2 launch can deliver SIGINT while rclpy cleanup is in flight.
            pass
        finally:
            try:
                if rclpy.ok():
                    rclpy.shutdown()
            except KeyboardInterrupt:
                pass
