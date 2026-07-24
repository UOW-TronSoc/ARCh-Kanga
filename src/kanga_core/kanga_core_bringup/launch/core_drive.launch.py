"""Initial core bringup: ODrive drive stack + /cmd_vel mapper.

Expects can_core already up on the host. Does not enter CLOSED_LOOP — call
drive_manager set_closed_loop after launch. This file will grow later
(description, battery, …); keep additions minimal for now.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    drive_share = get_package_share_directory("kanga_core_drive")
    controller_share = get_package_share_directory("kanga_core_controller")

    drive = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(drive_share, "launch", "drive.launch.py")
        )
    )

    controller = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(controller_share, "launch", "controller.launch.py")
        )
    )

    return LaunchDescription(
        [
            drive,
            controller,
        ]
    )
