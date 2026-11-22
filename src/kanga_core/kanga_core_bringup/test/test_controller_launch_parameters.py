"""Standalone controller.launch.py loads /core/wheel_command_mapper once."""

from pathlib import Path
import unittest

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
import launch_testing
import pytest
from rcl_interfaces.srv import GetParameters
import rclpy


@pytest.mark.launch_test
def generate_test_description():
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(
                        Path(get_package_share_directory("kanga_core_controller"))
                        / "launch"
                        / "controller.launch.py"
                    )
                )
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestStandaloneController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = rclpy.create_node("controller_launch_probe")

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def test_mapper_parameters(self):
        for _ in range(50):
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if ("wheel_command_mapper", "/core") in self.node.get_node_names_and_namespaces():
                break
        matches = [
            item
            for item in self.node.get_node_names_and_namespaces()
            if item[0] == "wheel_command_mapper"
        ]
        self.assertEqual(matches, [("wheel_command_mapper", "/core")])
        client = self.node.create_client(
            GetParameters, "/core/wheel_command_mapper/get_parameters"
        )
        self.assertTrue(client.wait_for_service(timeout_sec=15.0))
        request = GetParameters.Request()
        request.names = [
            "max_linear_acceleration_m_s2",
            "max_angular_acceleration_rad_s2",
        ]
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=5.0)
        values = future.result().values
        self.assertEqual(values[0].double_value, 0.35)
        self.assertEqual(values[1].double_value, 0.35)
