"""Start the small onboard process-ownership agent."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(
                package="kanga_launch_agent",
                executable="launch_agent",
                name="kanga_launch_agent",
                output="screen",
            )
        ]
    )
