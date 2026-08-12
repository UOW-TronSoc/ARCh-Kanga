"""Start ROS joy and the Kanga bench-only joystick teleop node."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


# Launch the standard joystick driver and bench teleop mapping.
def generate_launch_description():
    device_id = LaunchConfiguration("device_id")
    bench_config = os.path.join(
        get_package_share_directory("kanga_joy"),
        "config",
        "bench_teleop.yaml",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "device_id",
                default_value="0",
                description="SDL controller index used by joy_node",
            ),
            Node(
                package="joy",
                executable="joy_node",
                name="joy_node",
                parameters=[
                    {
                        "device_id": ParameterValue(device_id, value_type=int),
                        "deadzone": 0.05,
                        "autorepeat_rate": 20.0,
                    }
                ],
                output="screen",
            ),
            Node(
                package="kanga_joy",
                executable="bench_teleop",
                name="bench_teleop",
                parameters=[bench_config],
                output="screen",
                emulate_tty=True,
            ),
        ]
    )
