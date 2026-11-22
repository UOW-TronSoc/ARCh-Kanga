"""Load installed Core YAML through the real launch files and read the nodes."""

from pathlib import Path
import unittest

from ament_index_python.packages import get_package_share_directory
import pytest
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
import launch_testing
from rcl_interfaces.srv import GetParameters
import rclpy


def _include(package, launch_file, arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(Path(get_package_share_directory(package)) / "launch" / launch_file)
        ),
        launch_arguments=arguments or {},
    )


def _double(node, target, name):
    client = node.create_client(GetParameters, f"{target}/get_parameters")
    assert client.wait_for_service(timeout_sec=15.0), target
    request = GetParameters.Request()
    request.names = [name]
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
    return future.result().values[0].double_value


def _string(node, target, name):
    client = node.create_client(GetParameters, f"{target}/get_parameters")
    assert client.wait_for_service(timeout_sec=15.0), target
    request = GetParameters.Request()
    request.names = [name]
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
    return future.result().values[0].string_value


def _string_array(node, target, name):
    client = node.create_client(GetParameters, f"{target}/get_parameters")
    assert client.wait_for_service(timeout_sec=15.0), target
    request = GetParameters.Request()
    request.names = [name]
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
    return list(future.result().values[0].string_array_value)


def _integer(node, target, name):
    client = node.create_client(GetParameters, f"{target}/get_parameters")
    assert client.wait_for_service(timeout_sec=15.0), target
    request = GetParameters.Request()
    request.names = [name]
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
    return future.result().values[0].integer_value


@pytest.mark.launch_test
def generate_test_description():
    return LaunchDescription(
        [
            _include("kanga_core_controller", "controller.launch.py"),
            _include("kanga_core_drive", "drive.launch.py"),
            _include("kanga_core_microcontroller", "suspension_state.launch.py"),
            _include(
                "kanga_core_microcontroller",
                "body_pose_tf.launch.py",
                {"body_pose_child_frame": "measured_body"}.items(),
            ),
            _include(
                "kanga_core_microcontroller",
                "core_can_bridge.launch.py",
                {
                    "launch_socketcan": "false",
                    "imu_frame_id": "imu_link_test",
                }.items(),
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestCoreParameterLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = rclpy.create_node("core_parameter_probe")

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def test_each_core_node_appears_once_under_core(self):
        deadline_spins = 50
        expected = {
            "wheel_command_mapper",
            "wheel_actuator",
            "wheel_joint_state_publisher",
            "core_can_bridge",
            "suspension_joint_state_publisher",
            "body_pose_tf_broadcaster",
        }
        found = set()
        for _ in range(deadline_spins):
            rclpy.spin_once(self.node, timeout_sec=0.1)
            found = {
                name
                for name, namespace in self.node.get_node_names_and_namespaces()
                if namespace == "/core"
            }
            if expected <= found:
                break
        for name in expected:
            count = [
                item
                for item in self.node.get_node_names_and_namespaces()
                if item == (name, "/core")
            ]
            self.assertEqual(len(count), 1, name)

    def test_yaml_values_and_launch_overrides_are_loaded(self):
        self.assertEqual(
            _double(self.node, "/core/wheel_command_mapper", "max_linear_acceleration_m_s2"),
            0.35,
        )
        self.assertEqual(
            _double(self.node, "/core/wheel_command_mapper", "max_angular_acceleration_rad_s2"),
            0.35,
        )
        # Profile dictionary overrides the YAML file on the same node.
        self.assertEqual(
            _double(self.node, "/core/wheel_command_mapper", "grouser_angle_deg"),
            51.0,
        )
        self.assertEqual(
            _double(self.node, "/core/wheel_actuator", "publish_rate_hz"),
            50.0,
        )
        self.assertEqual(
            _string_array(self.node, "/core/wheel_actuator", "wheel_ids"),
            ["fl", "bl", "br", "fr"],
        )
        self.assertEqual(
            _double(self.node, "/core/wheel_joint_state_publisher", "publish_rate_hz"),
            50.0,
        )
        self.assertEqual(
            _integer(self.node, "/core/core_can_bridge", "diff_bar_encoder_zero_count"),
            1063,
        )
        self.assertAlmostEqual(
            _double(self.node, "/core/core_can_bridge", "diff_bar_encoder_counts_per_rad"),
            651.8986469044033,
        )
        self.assertEqual(
            _string(self.node, "/core/core_can_bridge", "imu_frame_id"),
            "imu_link_test",
        )
        self.assertAlmostEqual(
            _double(
                self.node,
                "/core/suspension_joint_state_publisher",
                "diff_bar_limit_rad",
            ),
            1.2217304763960306,
        )
        self.assertAlmostEqual(
            _double(
                self.node,
                "/core/suspension_joint_state_publisher",
                "suspension_linkage_l1_mm",
            ),
            545.5,
        )
        self.assertEqual(
            _double(self.node, "/core/body_pose_tf_broadcaster", "quaternion_norm_tolerance"),
            0.01,
        )
        self.assertEqual(
            _string(self.node, "/core/body_pose_tf_broadcaster", "child_frame_id"),
            "measured_body",
        )

    def test_can_transport_stays_at_the_root(self):
        deadline = 30
        attached = False
        for _ in range(deadline):
            rclpy.spin_once(self.node, timeout_sec=0.1)
            root = {
                info.node_name
                for info in self.node.get_subscriptions_info_by_topic("/from_can_bus")
            }
            nested = {
                info.node_name
                for info in self.node.get_subscriptions_info_by_topic("/core/from_can_bus")
            }
            attached = "core_can_bridge" in root and "core_can_bridge" not in nested
            if attached:
                break
        self.assertTrue(attached)
