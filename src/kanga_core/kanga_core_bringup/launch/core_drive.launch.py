"""Initial core bringup: ODrive drive stack + /cmd_vel mapper.

Expects its selected CAN interface (can_core by default) already up on the host.
Does not enter CLOSED_LOOP — call drive_manager set_closed_loop after launch.
This file will grow later (description, battery, …); keep additions minimal.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from kanga_core_description.drivetrain_profile import DEFAULT_DRIVETRAIN_PROFILE  # pyright: ignore[reportMissingImports]
from kanga_core_description.motor_limits import DEFAULT_MOTOR_LIMITS  # pyright: ignore[reportMissingImports]


# Forward the shared physical profile and operating limits to both consumers.
def generate_launch_description():
    drive_share = get_package_share_directory("kanga_core_drive")
    controller_share = get_package_share_directory("kanga_core_controller")
    can_interface = LaunchConfiguration("can_interface")
    drivetrain_profile = LaunchConfiguration("drivetrain_profile")
    motor_limits = LaunchConfiguration("motor_limits")

    drive = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(drive_share, "launch", "drive.launch.py")
        ),
        launch_arguments={
            "can_interface": can_interface,
            "drivetrain_profile": drivetrain_profile,
            "motor_limits": motor_limits,
        }.items(),
    )

    controller = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(controller_share, "launch", "controller.launch.py")
        ),
        launch_arguments={
            "drivetrain_profile": drivetrain_profile,
            "motor_limits": motor_limits,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "can_interface",
                default_value="can_core",
                description="Host SocketCAN interface used by the drive ODrives",
            ),
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Core drivetrain profile from kanga_core_description",
            ),
            DeclareLaunchArgument(
                "motor_limits",
                default_value=DEFAULT_MOTOR_LIMITS,
                description="Core operating-limit config id or YAML path",
            ),
            drive,
            controller,
        ]
    )
