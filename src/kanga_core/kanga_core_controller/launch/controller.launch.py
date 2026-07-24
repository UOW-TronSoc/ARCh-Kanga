"""Start the wheel_command_mapper node with config/controller.yaml.

Beginner flow:
  1. Launch motors first:
       ros2 launch kanga_core_drive drive.launch.py
  2. Launch this file:
       ros2 launch kanga_core_controller controller.launch.py
  3. Enter CLOSED_LOOP (drive_manager set_closed_loop), then publish /cmd_vel.

This launch file only starts the mapper. It does not bring up CAN, ODrives,
or closed-loop mode.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # Installed copy of config/controller.yaml (share/kanga_core_controller/…).
    params = os.path.join(
        get_package_share_directory("kanga_core_controller"),
        "config",
        "controller.yaml",
    )

    wheel_command_mapper = Node(
        package="kanga_core_controller",
        executable="wheel_command_mapper",
        name="wheel_command_mapper",
        parameters=[params],
        output="screen",
    )

    return LaunchDescription(
        [
            wheel_command_mapper,
        ]
    )
