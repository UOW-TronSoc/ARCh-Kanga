# This unified launch is a development and testing ground. When the rover is
# production-ready, add a separate lightweight production launch instead of
# stripping the useful diagnostics and visualisation options from this file.
"""Compose the currently available physical Kanga core packages."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from kanga_core_description.drivetrain_profile import DEFAULT_DRIVETRAIN_PROFILE


def _include(package_name, launch_file, *, arguments=None, condition=None):
    """Create a compact include for one installed package launch file."""
    package_share = get_package_share_directory(package_name)
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_share, "launch", launch_file)
        ),
        launch_arguments=(arguments or {}).items(),
        condition=condition,
    )


def generate_launch_description():
    can_interface = LaunchConfiguration("can_interface")
    drivetrain_profile = LaunchConfiguration("drivetrain_profile")
    use_drive = LaunchConfiguration("use_drive")
    use_controller = LaunchConfiguration("use_controller")
    use_suspension_state = LaunchConfiguration("use_suspension_state")
    use_joint_state_publisher = LaunchConfiguration("use_joint_state_publisher")
    use_gui = LaunchConfiguration("use_gui")
    use_rviz = LaunchConfiguration("use_rviz")
    use_onboard_control = LaunchConfiguration("use_onboard_control")
    device_id = LaunchConfiguration("device_id")
    joint_state_sources = LaunchConfiguration("joint_state_sources")

    description = _include(
        "kanga_core_description",
        "view_core_2026.launch.py",
        arguments={
            "drivetrain_profile": drivetrain_profile,
            "use_joint_state_publisher": use_joint_state_publisher,
            "use_gui": use_gui,
            "use_rviz": use_rviz,
            "joint_state_sources": joint_state_sources,
        },
    )

    drive = _include(
        "kanga_core_drive",
        "drive.launch.py",
        arguments={
            "can_interface": can_interface,
            "drivetrain_profile": drivetrain_profile,
        },
        condition=IfCondition(use_drive),
    )

    controller = _include(
        "kanga_core_controller",
        "controller.launch.py",
        arguments={"drivetrain_profile": drivetrain_profile},
        condition=IfCondition(use_controller),
    )

    suspension_state = _include(
        "kanga_core_microcontroller",
        "suspension_state.launch.py",
        condition=IfCondition(use_suspension_state),
    )

    # Temporary local-control implementation until kanga_onboard_control gains
    # its production launch. This is deliberately disabled by default.
    onboard_control = _include(
        "kanga_joy",
        "bench_teleop.launch.py",
        arguments={"device_id": device_id},
        condition=IfCondition(use_onboard_control),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "can_interface",
                default_value="can_core",
                description="Host SocketCAN interface used by the core ODrives",
            ),
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Core drivetrain profile from kanga_core_description",
            ),
            DeclareLaunchArgument(
                "use_drive",
                default_value="true",
                description="Start the physical ODrive stack and drive manager",
            ),
            DeclareLaunchArgument(
                "use_controller",
                default_value="true",
                description="Start the /cmd_vel to wheel-command controller",
            ),
            DeclareLaunchArgument(
                "use_suspension_state",
                default_value="true",
                description="Start differential-bar suspension state mapping",
            ),
            DeclareLaunchArgument(
                "use_joint_state_publisher",
                default_value="false",
                description=(
                    "Merge wheel and suspension state topics into /joint_states"
                ),
            ),
            DeclareLaunchArgument(
                "use_gui",
                default_value="false",
                description=(
                    "Use joint-state sliders; ignored unless "
                    "use_joint_state_publisher is true"
                ),
            ),
            DeclareLaunchArgument(
                "joint_state_sources",
                default_value=(
                    '["wheel_joint_states", "suspension_joint_states"]'
                ),
                description="JointState topics merged into /joint_states",
            ),
            DeclareLaunchArgument(
                "use_rviz",
                default_value="false",
                description="Start RViz with the core_2026 configuration",
            ),
            DeclareLaunchArgument(
                "use_onboard_control",
                default_value="false",
                description="Start the provisional local gamepad control path",
            ),
            DeclareLaunchArgument(
                "device_id",
                default_value="0",
                description="SDL game-controller index for onboard control",
            ),
            description,
            drive,
            controller,
            suspension_state,
            onboard_control,
        ]
    )
