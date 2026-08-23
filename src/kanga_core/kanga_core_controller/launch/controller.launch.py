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
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from kanga_core_description.drivetrain_profile import (
    DEFAULT_DRIVETRAIN_PROFILE,
    load_drivetrain_profile,
)


# Load the selected profile and create the wheel-command mapper node.
def _launch_setup(context):
    profile_ref = LaunchConfiguration("drivetrain_profile").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time")
    profile = load_drivetrain_profile(profile_ref)


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
        # Every consumer receives the same shared profile dictionary. The node
        # declares and reads only the parameters it actually uses.
        parameters=[params, profile.parameters, {"use_sim_time": use_sim_time}],
        output="screen",
    )

    return [
        LogInfo(
            msg=f"Controller using {profile.profile_id} ({profile.display_name})"
        ),
        wheel_command_mapper,
    ]


# Declare the profile argument and defer node creation until launch evaluation.
def generate_launch_description():

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Drivetrain profile id from kanga_core_description",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="false",
                description="Use the ROS simulation clock",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
