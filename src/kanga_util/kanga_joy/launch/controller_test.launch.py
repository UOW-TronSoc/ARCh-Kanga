"""Start the standard ROS 2 joystick driver and Kanga input monitor."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


# Launch joy_node and the readable controller event monitor.
def generate_launch_description():
    device_id = LaunchConfiguration("device_id")

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
                executable="controller_test",
                name="controller_test",
                output="screen",
                emulate_tty=True,
            ),
        ]
    )
