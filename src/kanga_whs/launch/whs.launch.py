"""Launch the software whole-robot stop node (publishes /drivestop)."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    initial_drivestop = LaunchConfiguration("initial_drivestop")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "initial_drivestop",
                default_value="true",
                description=(
                    "Initial software motion inhibit. Production should remain "
                    "true so startup requires an explicit release."
                ),
            ),
            Node(
                package="kanga_whs",
                executable="whs_node",
                name="whs_node",
                parameters=[
                    {
                        "initial_drivestop": ParameterValue(
                            initial_drivestop, value_type=bool
                        )
                    }
                ],
                output="screen",
            ),
        ]
    )
