"""Start differential-bar to suspension JointState mapping."""

from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    parameters = PathJoinSubstitution(
        [
            FindPackageShare("kanga_core_microcontroller"),
            "config",
            "suspension_state.yaml",
        ]
    )

    return LaunchDescription(
        [
            Node(
                package="kanga_core_microcontroller",
                executable="suspension_joint_state_publisher",
                name="suspension_joint_state_publisher",
                parameters=[parameters],
                output="screen",
            )
        ]
    )
