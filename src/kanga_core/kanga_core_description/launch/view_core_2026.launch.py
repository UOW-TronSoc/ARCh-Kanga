"""Display the standalone core_2026 model with joint controls and RViz."""

from typing import List

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    AndSubstitution,
    Command,
    LaunchConfiguration,
    NotSubstitution,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    drivetrain_profile = LaunchConfiguration("drivetrain_profile")
    use_joint_state_publisher = LaunchConfiguration("use_joint_state_publisher")
    use_gui = LaunchConfiguration("use_gui")
    use_rviz = LaunchConfiguration("use_rviz")
    joint_state_sources = ParameterValue(
        LaunchConfiguration("joint_state_sources"), value_type=List[str]
    )

    model_path = PathJoinSubstitution(
        [FindPackageShare("kanga_core_description"), "urdf", "core_2026.urdf.xacro"]
    )
    rviz_config = PathJoinSubstitution(
        [FindPackageShare("kanga_core_description"), "rviz", "core_2026.rviz"]
    )
    visualization_parameters = PathJoinSubstitution(
        [FindPackageShare("kanga_core_description"), "config", "visualization.yaml"]
    )
    robot_description = ParameterValue(
        Command(
            [
                "xacro ",
                model_path,
                " drivetrain_profile:=",
                drivetrain_profile,
            ]
        ),
        value_type=str,
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value="drivetrain_2025",
                description="Physical drivetrain profile used by core_2026",
            ),
            DeclareLaunchArgument(
                "use_joint_state_publisher",
                default_value="true",
                description="Start a joint-state publisher for movable joints",
            ),
            DeclareLaunchArgument(
                "use_gui",
                default_value="true",
                description="Use sliders when the joint-state publisher is enabled",
            ),
            DeclareLaunchArgument(
                "use_rviz",
                default_value="true",
                description="Start RViz with the core_2026 view",
            ),
            DeclareLaunchArgument(
                "joint_state_sources",
                default_value=(
                    '["wheel_joint_states", "suspension_joint_states"]'
                ),
                description=(
                    "JointState topics merged by joint_state_publisher; missing "
                    "sources leave their joints at the neutral default"
                ),
            ),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="robot_state_publisher",
                parameters=[
                    visualization_parameters,
                    {"robot_description": robot_description},
                ],
                output="screen",
            ),
            Node(
                package="joint_state_publisher_gui",
                executable="joint_state_publisher_gui",
                name="joint_state_publisher",
                parameters=[
                    visualization_parameters,
                    {
                        "robot_description": robot_description,
                        "source_list": joint_state_sources,
                    }
                ],
                condition=IfCondition(
                    AndSubstitution(use_joint_state_publisher, use_gui)
                ),
                output="screen",
            ),
            Node(
                package="joint_state_publisher",
                executable="joint_state_publisher",
                name="joint_state_publisher",
                parameters=[
                    visualization_parameters,
                    {
                        "robot_description": robot_description,
                        "source_list": joint_state_sources,
                    }
                ],
                condition=IfCondition(
                    AndSubstitution(
                        use_joint_state_publisher, NotSubstitution(use_gui)
                    )
                ),
                output="screen",
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                arguments=["-d", rviz_config],
                condition=IfCondition(use_rviz),
                output="screen",
            ),
        ]
    )
