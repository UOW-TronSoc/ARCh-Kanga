"""Launch the software whole-robot stop node (publishes /drivestop)."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="kanga_whs",
                executable="whs_node",
                name="whs_node",
                output="screen",
            ),
        ]
    )
