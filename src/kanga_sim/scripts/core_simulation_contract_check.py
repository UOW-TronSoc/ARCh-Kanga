#!/usr/bin/env python3
"""Headless operational-interface smoke test for a running core simulation."""

from __future__ import annotations

import math
import sys
import time

from geometry_msgs.msg import (
    PoseWithCovarianceStamped,
    Twist,
    TwistWithCovarianceStamped,
)
from kanga_interfaces.msg import WheelVelocityCommand
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from std_srvs.srv import SetBool, Trigger
from tf2_msgs.msg import TFMessage


EXPECTED_TOPICS = {
    "/wheel_joint_velocity_command": "kanga_interfaces/msg/WheelVelocityCommand",
    "/drivestop": "std_msgs/msg/Bool",
    "/wheel_joint_states": "sensor_msgs/msg/JointState",
    "/suspension_joint_states": "sensor_msgs/msg/JointState",
    "/diff_bar_angle": "std_msgs/msg/Float64",
    "/body/pose": "geometry_msgs/msg/PoseWithCovarianceStamped",
    "/body/twist": "geometry_msgs/msg/TwistWithCovarianceStamped",
    "/odom": "nav_msgs/msg/Odometry",
    "/joint_states": "sensor_msgs/msg/JointState",
    "/robot_description": "std_msgs/msg/String",
    "/tf": "tf2_msgs/msg/TFMessage",
    "/tf_static": "tf2_msgs/msg/TFMessage",
    "/clock": "rosgraph_msgs/msg/Clock",
}
EXPECTED_SERVICES = {
    "/whs_node/set_drivestop": "std_srvs/srv/SetBool",
    "/drive_manager/set_closed_loop": "std_srvs/srv/SetBool",
    "/drive_manager/clear_errors": "std_srvs/srv/Trigger",
    "/drive_manager/save_fl": "std_srvs/srv/Trigger",
    "/drive_manager/save_bl": "std_srvs/srv/Trigger",
    "/drive_manager/save_br": "std_srvs/srv/Trigger",
    "/drive_manager/save_fr": "std_srvs/srv/Trigger",
    "/drive_manager/calibrate_fl": "std_srvs/srv/Trigger",
    "/drive_manager/calibrate_bl": "std_srvs/srv/Trigger",
    "/drive_manager/calibrate_br": "std_srvs/srv/Trigger",
    "/drive_manager/calibrate_fr": "std_srvs/srv/Trigger",
}


class ContractCheck(Node):
    def __init__(self) -> None:
        super().__init__("core_simulation_contract_check")
        self.wheel_messages: list[JointState] = []
        self.wheel_commands: list[WheelVelocityCommand] = []
        self.suspension_message: JointState | None = None
        self.diff_bar_message: Float64 | None = None
        self.pose_message: PoseWithCovarianceStamped | None = None
        self.twist_message: TwistWithCovarianceStamped | None = None
        self.odom_message: Odometry | None = None
        self.joint_message: JointState | None = None
        self.clock_message: Clock | None = None
        self.tf_pairs: set[tuple[str, str]] = set()

        self.cmd_vel_publisher = self.create_publisher(Twist, "/cmd_vel", 10)

        self.create_subscription(
            WheelVelocityCommand,
            "/wheel_joint_velocity_command",
            self.wheel_commands.append,
            100,
        )
        self.create_subscription(
            JointState, "/wheel_joint_states", self.wheel_messages.append, 100
        )
        self.create_subscription(
            JointState,
            "/suspension_joint_states",
            lambda message: setattr(self, "suspension_message", message),
            10,
        )
        self.create_subscription(
            Float64,
            "/diff_bar_angle",
            lambda message: setattr(self, "diff_bar_message", message),
            10,
        )
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/body/pose",
            lambda message: setattr(self, "pose_message", message),
            10,
        )
        self.create_subscription(
            TwistWithCovarianceStamped,
            "/body/twist",
            lambda message: setattr(self, "twist_message", message),
            10,
        )
        self.create_subscription(
            Odometry,
            "/odom",
            lambda message: setattr(self, "odom_message", message),
            10,
        )
        self.create_subscription(
            JointState,
            "/joint_states",
            lambda message: setattr(self, "joint_message", message),
            10,
        )
        self.create_subscription(
            Clock,
            "/clock",
            lambda message: setattr(self, "clock_message", message),
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        self.create_subscription(TFMessage, "/tf", self._on_tf, 100)
        self.create_subscription(
            TFMessage,
            "/tf_static",
            self._on_tf,
            QoSProfile(
                depth=100,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )

    def _on_tf(self, message: TFMessage) -> None:
        for transform in message.transforms:
            self.tf_pairs.add((transform.header.frame_id, transform.child_frame_id))

    def wait_for_state(self, timeout_s: float = 20.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if len(self.wheel_messages) >= 55:
                first = self.wheel_messages[0].header.stamp
                last = self.wheel_messages[-1].header.stamp
                span = (last.sec - first.sec) + (last.nanosec - first.nanosec) * 1e-9
                if span >= 1.0:
                    return
        raise AssertionError("timed out waiting for one simulated second of state")

    def call_trigger(self, name: str) -> Trigger.Response:
        client = self.create_client(Trigger, name)
        assert client.wait_for_service(timeout_sec=5.0), f"missing service {name}"
        future = client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        response = future.result()
        assert response is not None, f"no response from {name}"
        return response

    def call_closed_loop(self, enable: bool) -> SetBool.Response:
        client = self.create_client(SetBool, "/drive_manager/set_closed_loop")
        assert client.wait_for_service(timeout_sec=5.0)
        request = SetBool.Request()
        request.data = enable
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        response = future.result()
        assert response is not None
        return response

    def call_drivestop(self, active: bool) -> SetBool.Response:
        client = self.create_client(SetBool, "/whs_node/set_drivestop")
        assert client.wait_for_service(timeout_sec=5.0)
        request = SetBool.Request()
        request.data = active
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        response = future.result()
        assert response is not None
        return response

    def run_for_simulated_seconds(
        self, duration_s: float, command: Twist | None = None
    ) -> None:
        assert self.clock_message is not None
        start = clock_seconds(self.clock_message)
        wall_deadline = time.monotonic() + max(10.0, duration_s * 5.0)
        while clock_seconds(self.clock_message) - start < duration_s:
            if time.monotonic() >= wall_deadline:
                raise AssertionError("simulation clock stopped during behavior check")
            if command is not None:
                self.cmd_vel_publisher.publish(command)
            rclpy.spin_once(self, timeout_sec=0.02)


def stamp_seconds(message: JointState) -> float:
    return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9


def clock_seconds(message: Clock) -> float:
    return message.clock.sec + message.clock.nanosec * 1e-9


def twist(x: float = 0.0, y: float = 0.0, yaw: float = 0.0) -> Twist:
    command = Twist()
    command.linear.x = x
    command.linear.y = y
    command.angular.z = yaw
    return command


def command_values(command: WheelVelocityCommand) -> list[float]:
    return [
        command.front_left_rad_s,
        command.back_left_rad_s,
        command.back_right_rad_s,
        command.front_right_rad_s,
    ]


def run_checks(node: ContractCheck) -> None:
    node.wait_for_state()

    topics = {name: types for name, types in node.get_topic_names_and_types()}
    for name, expected_type in EXPECTED_TOPICS.items():
        assert topics.get(name) == [expected_type], (name, topics.get(name))
    services = {name: types for name, types in node.get_service_names_and_types()}
    for name, expected_type in EXPECTED_SERVICES.items():
        assert services.get(name) == [expected_type], (name, services.get(name))

    latest_wheel = node.wheel_messages[-1]
    assert latest_wheel.name == [
        "wheel_fl_joint",
        "wheel_bl_joint",
        "wheel_br_joint",
        "wheel_fr_joint",
    ]
    assert len(latest_wheel.position) == len(latest_wheel.velocity) == 4
    assert node.suspension_message is not None
    assert node.suspension_message.name == [
        "diff_bar_joint",
        "left_suspension_joint",
        "right_suspension_joint",
    ]
    assert len(node.suspension_message.position) == 3
    assert node.diff_bar_message is not None
    # Gazebo only publishes the encoder angle; kinematics owns the joint states.
    assert abs(
        node.suspension_message.position[1] - node.suspension_message.position[2]
    ) < 1e-9
    if abs(node.diff_bar_message.data) <= 1.2217304763960306 + 1e-9:
        assert abs(
            node.suspension_message.position[0] - node.diff_bar_message.data
        ) < 1e-6
    suspension_publishers = [
        endpoint.node_name
        for endpoint in node.get_publishers_info_by_topic("/suspension_joint_states")
    ]
    assert "suspension_joint_state_publisher" in suspension_publishers
    assert "drive_manager" not in suspension_publishers
    diff_bar_publishers = [
        endpoint.node_name
        for endpoint in node.get_publishers_info_by_topic("/diff_bar_angle")
    ]
    assert "drive_manager" in diff_bar_publishers
    assert "suspension_joint_state_publisher" not in diff_bar_publishers
    assert node.pose_message is not None
    assert node.pose_message.header.frame_id == "body_origin"
    assert abs(node.pose_message.pose.pose.position.x) < 1e-9
    assert abs(node.pose_message.pose.pose.position.y) < 1e-9
    assert abs(node.pose_message.pose.pose.position.z) < 1e-9
    assert node.pose_message.pose.covariance[0] >= 1.0e6
    assert node.pose_message.pose.covariance[7] >= 1.0e6
    assert node.pose_message.pose.covariance[14] >= 1.0e6
    assert node.twist_message is not None
    assert node.twist_message.header.frame_id == "base_link"
    assert abs(node.twist_message.twist.twist.linear.x) < 1e-9
    assert abs(node.twist_message.twist.twist.linear.y) < 1e-9
    assert abs(node.twist_message.twist.twist.linear.z) < 1e-9
    assert node.odom_message is not None
    assert node.odom_message.header.frame_id == "odom"
    assert node.odom_message.child_frame_id == "base_link"
    assert node.joint_message is not None
    assert node.clock_message is not None

    sample = node.wheel_messages[-51:]
    span = stamp_seconds(sample[-1]) - stamp_seconds(sample[0])
    rate_hz = (len(sample) - 1) / span
    assert 47.0 <= rate_hz <= 53.0, f"wheel state rate was {rate_hz:.2f} Hz"

    assert ("body_origin", "base_link") in node.tf_pairs
    base_parents = {parent for parent, child in node.tf_pairs if child == "base_link"}
    assert base_parents == {"body_origin"}, base_parents
    assert ("odom", "base_link") not in node.tf_pairs

    drive_stop_endpoints = [
        endpoint
        for endpoint in node.get_subscriptions_info_by_topic("/drivestop")
        if endpoint.node_name == "drive_manager"
    ]
    assert len(drive_stop_endpoints) == 1
    endpoint = drive_stop_endpoints[0]
    assert endpoint.qos_profile.reliability == ReliabilityPolicy.RELIABLE
    assert endpoint.qos_profile.durability == DurabilityPolicy.TRANSIENT_LOCAL
    drivestop_publishers = [
        endpoint.node_name
        for endpoint in node.get_publishers_info_by_topic("/drivestop")
    ]
    assert drivestop_publishers == ["whs_node"], drivestop_publishers

    assert node.call_trigger("/drive_manager/clear_errors").success
    for wheel in ["fl", "bl", "br", "fr"]:
        save_response = node.call_trigger(f"/drive_manager/save_{wheel}")
        assert save_response.success
        assert save_response.message == (
            "configuration persistence not required in simulation"
        )
        response = node.call_trigger(f"/drive_manager/calibrate_{wheel}")
        assert response.success
        assert response.message == "calibration not required in simulation"

    # Exercise the unchanged controller while the simulated drive remains IDLE.
    # This verifies the live field ordering and directional sign contract without
    # relying on the simplified wheel collision to reproduce every grouser force.
    idle_start_x = node.odom_message.pose.pose.position.x
    idle_start_y = node.odom_message.pose.pose.position.y
    directional_cases = [
        (twist(x=0.08), [1, 1, 1, 1]),
        (twist(y=0.05), [1, -1, 1, -1]),
        (twist(yaw=0.05), [-1, -1, 1, 1]),
        (twist(x=0.02, y=0.04, yaw=0.02), [1, -1, 1, 1]),
        (twist(x=-0.08), [-1, -1, -1, -1]),
    ]
    for body_command, expected_signs in directional_cases:
        node.run_for_simulated_seconds(0.5, body_command)
        assert node.wheel_commands
        values = command_values(node.wheel_commands[-1])
        assert all(
            math.copysign(1.0, value) == expected_sign
            and abs(value) > 1e-3
            for value, expected_sign in zip(values, expected_signs)
        ), (values, expected_signs)

    node.run_for_simulated_seconds(0.75)
    assert all(abs(value) < 1e-6 for value in command_values(node.wheel_commands[-1]))
    idle_distance = math.hypot(
        node.odom_message.pose.pose.position.x - idle_start_x,
        node.odom_message.pose.pose.position.y - idle_start_y,
    )
    assert idle_distance < 0.025, f"IDLE rover moved {idle_distance:.3f} m"

    # Exercise drivestop through its sole authority instead of publishing a
    # competing transient-local value from the contract test. WHS must fail
    # closed on startup, so motion cannot be enabled before an explicit release.
    rejected_initial_enable = node.call_closed_loop(True)
    assert not rejected_initial_enable.success
    assert rejected_initial_enable.message == "drivestop is active"
    assert node.call_drivestop(False).success
    node.run_for_simulated_seconds(0.1)
    assert node.call_closed_loop(True).success
    motion_start_x = node.odom_message.pose.pose.position.x
    node.run_for_simulated_seconds(1.0, twist(x=0.10))
    assert node.odom_message.pose.pose.position.x - motion_start_x > 0.02
    assert all(velocity > 0.05 for velocity in node.wheel_messages[-1].velocity)

    assert node.call_drivestop(True).success
    node.run_for_simulated_seconds(0.1, twist(x=0.10))
    rejected_enable = node.call_closed_loop(True)
    assert not rejected_enable.success
    assert rejected_enable.message == "drivestop is active"

    assert node.call_drivestop(False).success
    node.run_for_simulated_seconds(0.1)
    idle_response = node.call_closed_loop(False)
    assert idle_response.success
    assert idle_response.message == "all wheels idle"


def main() -> int:
    rclpy.init()
    node = ContractCheck()
    try:
        run_checks(node)
    except Exception as error:  # noqa: BLE001 - executable should report all failures.
        node.get_logger().error(f"core simulation contract failed: {error}")
        return 1
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print("Core simulation operational interface contract passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
